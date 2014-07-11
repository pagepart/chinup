from __future__ import absolute_import, unicode_literals

import logging
import threading

from .lowlevel import batch_request
from . import settings


logger = logging.getLogger(__name__)


_threadlocals = threading.local()


def get_queue(app_token):
    try:
        qs = _threadlocals.chinup_queues
    except AttributeError:
        qs = _threadlocals.chinup_queues = {}
    try:
        q = qs[app_token]
    except KeyError:
        q = qs[app_token] = ChinupQueue(app_token)
    return q


def reset_queue(app_token):
    try:
        del _threadlocals.chinup_queues[app_token]
    except (AttributeError, KeyError):
        pass


def delete_queues():
    try:
        del _threadlocals.chinup_queues
    except AttributeError:
        pass


class ChinupQueue(object):
    """
    List of pending Chinups with a common app token.
    """
    def __init__(self, app_token):
        self.app_token = app_token
        self.chinups = []

    def append(self, req):
        self.chinups.append(req)

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

        # Some requests in the batch might time out rather than completing.
        # Continue batching until the calling chinup is satisfied, or until we
        # stop making progress.
        progress = 1
        chinups = [cu for cu in chinups if not cu.completed]

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
            responses = batch_request(self.app_token, requests)

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

        if caller and not caller.completed:
            # Ugh, this means we timed out without making progress.
            caller.exception = QueueTimedOut("Couldn't make enough progress to complete request.")

        # Drop completed chinups from the queue to prevent clogging with
        # completed chinups. Put them on the front of the queue, rather than
        # replacing it entirely, in case there were callbacks (in the response
        # setter) that added to self.chinups.
        self.chinups[:0] = chinups

    def __getstate__(self):
        raise AssertionError("Why are you pickling a ChinupQueue?")
