from __future__ import absolute_import, unicode_literals

from collections import OrderedDict
import logging
import threading

from .lowlevel import batch_request
from .conf import settings
from .util import get_proof


logger = logging.getLogger(__name__)


_threadlocals = threading.local()


class ChinupQueue(object):
    """
    List of pending Chinups with a common app token.
    """
    def __new__(cls, app_token, **kwargs):
        try:
            qs = _threadlocals.chinup_queues
        except AttributeError:
            qs = _threadlocals.chinup_queues = {}
        try:
            q = qs[app_token]
        except KeyError:
            q = qs[app_token] = super(ChinupQueue, cls).__new__(
                cls, app_token, **kwargs)
            q.chinups = []
        return q

    def __init__(self, app_token, app_secret=None):
        self.app_token = app_token
        self.appsecret_proof = (get_proof(key=app_secret, msg=app_token)
                                if app_secret else None)
        # self.chinups set in __new__ for per-token singleton

    def __repr__(self):
        return '<{0.__class__.__name__} id={1} len={2} app_token={0.app_token}>'.format(
            self, id(self), len(self.chinups))

    def append(self, chinup, dedup=None):
        """
        Adds chinup to the queue.
        """
        logger.debug("Queuing %r", chinup)
        self.chinups.append(chinup)

    def sync(self, caller=None):
        """
        Builds and sends batch request, then populates Chinup responses.
        """
        if caller:
            assert caller in self.chinups

        # Take the existing queue from self.chinups. This is the max we will
        # try to accomplish in this sync, even if more are added during
        # processing (this can happen in chinup callback, or for paged
        # responses).
        chinups, self.chinups = self.chinups, []

        # Run prepare_batch() over the entire queue once before starting on
        # batches. This is an opportunity to replace users with tokens the most
        # efficiently, for example.
        if chinups:
            chinups, _ =  chinups[0].prepare_batch(chinups)

        # Deduplicate to get the list of unique chinups.
        if settings.DEDUP:
            chinups, dups = self.dedup(chinups)
        else:
            dups = None

        self._sync(chinups, caller)

        # Reduplicate the responses into the dups.
        if dups:
            chinups = self.redup(chinups, dups)

        if caller and not caller.completed:
            # Ugh, this means we timed out without making progress.
            caller.exception = QueueTimedOut("Couldn't make enough progress to complete request.")

        # Drop completed chinups from the queue to prevent clogging with
        # completed chinups. Put them on the front of the queue, rather than
        # replacing it entirely, in case there were callbacks (in the response
        # setter) that added to self.chinups.
        self.chinups[:0] = [cu for cu in chinups if not cu.completed]

    def _sync(self, chinups, caller):
        # Some requests in the batch might time out rather than completing.
        # Continue batching until the calling chinup is satisfied, or until we
        # stop making progress.
        progress = 1

        while chinups and progress and not (caller and caller.completed):

            # Ask the first chinup to process the chinups into a list of
            # request dicts. This is a classmethod, but calling via the first
            # chinup doesn't require us to know if Chinup has been subclassed.
            chinups, requests = chinups[0].prepare_batch(chinups)

            # It's possible that prepare_batch() decided all the chinups
            # were invalid, so make sure that we actually have requests.
            if not requests:
                assert not chinups
                logger.debug("No requests in batch after calling make_request_dicts()")
                break

            # Make the batch request.
            assert len(requests) <= 50
            logger.log(logging.INFO if settings.DEBUG_REQUESTS else logging.DEBUG,
                       "Making batch request len=%s/%s queue=%s",
                       len(requests), len(chinups), id(self))
            responses = batch_request(self.app_token, requests,
                                      appsecret_proof=self.appsecret_proof)

            # Populate responses into chinups.
            for cu, r in zip(chinups, responses):
                # Don't set response for timeouts, so they'll be automatically
                # tried again when .data is accessed.
                if r is not None:
                    cu.response = r
                logger.log(logging.INFO if settings.DEBUG_REQUESTS else logging.DEBUG,
                           '%s%r', 'TIMEOUT ' if r is None else '', cu)

            # Check for progress.
            progress = sum(1 for cu in chinups if cu.completed)

            # Filter out the completed chinups for the next pass.
            chinups = [cu for cu in chinups if not cu.completed]

    @classmethod
    def dedup(cls, chinups):
        """
        Returns (uniques, dups) where the latter is a dict of lists indexed by
        the former.
        """
        dups = OrderedDict()
        for c in chinups:
            clist = dups.setdefault(c, [])
            if clist:
                logger.debug("Dedup %r", c)
            clist.append(c)
        uniques = [clist[0] for clist in dups.values()]
        logger.debug("Deduping reduced from %s to %s.", len(chinups), len(uniques))
        return uniques, dups

    @classmethod
    def redup(cls, chinups, dups):
        """
        Returns full suite of chinups, integrating dups by setting their responses.
        """
        for cu in chinups:
            if not cu.completed:
                continue
            for i, dup in enumerate(dups[cu]):
                if i == 0:
                    assert dup is cu
                else:
                    assert not dup.completed
                    dup.response = cu.response
        return [cu for v in dups.values() for cu in v]

    def __getstate__(self):
        d = dict(self.__dict__)
        del d['chinups']
        return d

    def __getnewargs__(self):
        return (self.app_token,)

    def __setstate__(self, d):
        self.__dict__.update(d)


def delete_queues():
    try:
        del _threadlocals.chinup_queues
    except AttributeError:
        pass


__all__ = ['ChinupQueue', 'delete_queues']
