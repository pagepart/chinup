from __future__ import absolute_import, unicode_literals

import json
import logging
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

from urlobject import URLObject as URL

from .exceptions import ChinupCanceled, PagingError
from .lowlevel import parse_fb_exception
from .queue import ChinupQueue
from .util import partition, get_modattr, dev_inode
from . import settings


logger = logging.getLogger(__name__)


class Chinup(object):
    """
    A single FB request/response. This shouldn't be instantiated directly,
    rather the caller should use a ChinupBar:

        chinup = ChinupBar(token='XYZ').get('me')

    This returns a chinup which is a lazy request. It's on the queue and will
    be processed when convenient. The chinup can be access as follows:

        chinup.response = raw response from FB
        chinup.data = dict or list from FB, depending on endpoint
        chinup[key] = shortcut for chinup.data[key]
        key in chinup = shortcut for key in chinup.data

    The preferred method for accessing a list response is to iterate or listify
    the chinup directly. This will automatically advance through paged data,
    whereas accessing chinup.data will not.

        list(chinup)
            OR
        for d in chinup:
            do something clever with d
    """

    def __init__(self, queue, method, path, data, token=None,
                 raise_exceptions=True, callback=None, prefetch_next_page=True):
        self.queue = queue
        self.request = dict(method=method, path=path, data=data)
        self.token = token
        self.raise_exceptions = raise_exceptions
        self.callback = callback
        self.prefetch_next_page = prefetch_next_page
        self._response = None
        self._exception = None
        self._next_page = None

    def __unicode__(self, extra=''):
        r = self._response
        if (isinstance(r, dict) and r.get('code') == 200 and 'headers' in r and
                not settings.DEBUG_HEADERS):
            r = dict(r)
            del r['headers']
        return ('{0.request[method]} {0.request[path]} '
                '{2}data={0.request[data]} response={1!r}').format(
                    self, r, extra + ' ' if extra else '')

    def __repr__(self):
        return '<{0.__class__.__name__} id={1} {0} >'.format(self, id(self))

    @property
    def completed(self):
        """
        Returns False if this chinup remains to be synced, otherwise returns
        a truthy tuple of (response, exception).
        """
        comp = (self._response, self._exception)
        return any(x is not None for x in comp) and comp

    def _sync(self):
        if not self.completed:
            self.queue.sync(self)

    @property
    def response(self):
        self._sync()
        return self._response

    @response.setter
    def response(self, response):
        self._response = response

        # Decode and promote response body. The body can be None if the HTTP
        # status code isn't 200, for example 302 with a Location header.
        if isinstance(response, dict) and response.get('body') is not None:
            try:
                body = json.loads(response['body'])
            except ValueError as e:
                if not self._exception:
                    self._exception = e
            else:
                if (isinstance(body, dict) and ('data' in body or
                                                'error' in body)):
                    response.update(body)
                else:
                    response['data'] = body

                # Response body successfully decoded and promoted;
                # remove it from the dict to reduce confusion in logging etc.
                del response['body']

        # Keep parity with facepy exceptions.
        if not self._exception:
            self._exception = parse_fb_exception(response)

        # If this chinup has an associated callback, call it now. This allows
        # the caller to chain chinups, for example an async ads report. Don't
        # use this if you're not sure you need it.
        if self.callback:
            self.callback(self)

        # Prepare to fetch the next page.
        if self.prefetch_next_page:
            self.fetch_next_page()

    def _response_get(self, name):
        self._maybe_raise_exception()
        if isinstance(self.response, dict):
            return self.response.get(name)

    @property
    def data(self):
        return self._response_get('data')

    @property
    def error(self):
        return self._response_get('error')

    def cancel(self):
        self.exception = ChinupCanceled()

    @property
    def exception(self):
        self._sync()
        return self._exception

    @exception.setter
    def exception(self, value):
        self._exception = value

    def _maybe_raise_exception(self):
        if self.raise_exceptions and self.exception:
            logger.warning("Raising %s for %r", self.exception.__class__.__name__, self)
            raise self.exception

    def fetch_next_page(self):
        """
        Prepare to load the next page by putting a chinup on the queue.
        This doesn't actually do anything, of course, until .data or similar is
        accessed.
        """
        if self._next_page:
            return

        if not isinstance(self.response, dict):
            return

        try:
            next_link = self.response['paging']['next']
        except KeyError:
            return

        # FB provides a completely bogus "next" link to the insights call.
        if '/server.php' in next_link:
            return

        # FB can provide a "next" link when there's obviously nothing more.
        # Even worse, the "next" link on the adreportstats endpoint results in
        # a 500 error if you request past the end. Try to avoid that.
        limit = (self.response.get('limit') or
                 URL(next_link).query_dict.get('limit'))
        if limit and len(self.data) < int(limit):
            return

        # Putting this on the queue now enables
        # paging of one chinup to simultaneously prefetch paged data
        # for all chinups in the same queue.
        self._next_page = self._get_next_page(next_link)

    def _get_next_page(self, next_link, **kwargs):
        """
        Returns the chinup corresponding to the next page.
        This accepts kwargs for the sake of subclasses.
        """
        # Instantiate without token, since link already has it.
        next_chinup = self.__class__(
            queue=self.queue,
            method=self.request['method'],
            path=URL(next_link).with_scheme('').with_netloc('')[1:],
            data=None,  # all params are in next_link
            raise_exceptions=self.raise_exceptions,
            callback=self.callback,
            prefetch_next_page=self.prefetch_next_page,
            **kwargs)
        return next_chinup.queue.append(next_chinup)

    def next_page(self):
        """
        Returns the chinup corresponding to the next page, or None if
        il n'y en a pas.
        """
        self.fetch_next_page()
        return self._next_page

    def __iter__(self):
        """
        Yields successive records from self.data, advancing through paged data
        automatically.
        """
        chinup = self
        while chinup:  # will be None on last page
            if not isinstance(chinup.data, list):
                if not self.exception:
                    self.exception = PagingError("Unexpected chinup.data while paging")
                    self.exception.chinup = chinup
                    self._maybe_raise_exception()
                break
            for d in chinup.data:
                yield d
            chinup = chinup.next_page()

    def __len__(self):
        """
        Returns the length of data in this chinup, not all pages,
        to avoid infinite recursion because Python calls len(obj) as a first
        step to list(obj).
        """
        # If self.raise_exceptions is False, then self.data might be None.
        # Don't accidentally raise an exception here with len(None).
        return len(self.data or [])

    def __nonzero__(self):
        # Prevent truth value testing from calling len(self).
        return True

    def __getitem__(self, name):
        if isinstance(name, int) and isinstance(self.data, list):
            if name < len(self.data):
                return self.data[name]
            else:
                # Invoke paging
                return list(self)[name]
        return self.data[name]

    def get(self, name, default=None):
        return self.data.get(name, default)

    def __contains__(self, name):
        assert isinstance(self.data, dict)
        return name in self.data

    def __eq__(self, other):
        """
        Returns True if requests match. If both chinups are complete, then also
        compares their completion characteristics (response and exception).
        """
        if self.__class__ != other.__class__:
            logger.debug("__eq__ class mismatch")
            return False

        req, oreq = self._make_eq_dict(), other._make_eq_dict()
        if req != oreq:
            #logger.debug("__eq__ req mismatch")
            return False

        if self.callback:
            if (self.callback != other.callback or
                    self.completed != other.completed):
                logger.debug("__eq__ callback mismatch")
                return False

        if ((self.completed or other.completed) and
                self.completed != other.completed):
            logger.debug("__eq__ completed mismatch")
            return False

        return True

    def _make_eq_dict(self):
        """
        Returns a modified request dict suitable for comparing in __eq__.
        """
        req = self.make_request_dict()
        req['files'] = map(dev_inode, req.get('files', []))
        return req

    def items(self):
        return self.data.items()

    def __getstate__(self):
        if self.callback and self.completed:
            self.callback = None
        assert not self.callback, "can't pickle chinup with callback"
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)

        # Put it back on the current queue for app_token. This means it will be
        # considered for completion, but will be ignored if self.completed.
        self.queue.append(self, dedup=False)

    def make_request_dict(self):
        """
        Returns a dict suitable for a single request in a batch.
        """
        method = self.request['method']
        relative_url = URL(self.request['path'])
        data = self.request['data'] or {}

        if method == 'DEBUG_TOKEN':
            # This is a special case where access_token should NOT be set on
            # the relative_url, but should be passed as input_token instead.
            assert self.token, "can't debug_token without a token"
            method = 'GET'
            relative_url = URL('debug_token').set_query_params(
                input_token=self.token)

        elif self.token:
            relative_url = relative_url.set_query_params(
                access_token=self.token)

        if method != 'POST':
            # HACK since URLObject doesn't like ints in query values.
            data = {k: str(v) if isinstance(v, int) else v
                    for k, v in data.items()}
            relative_url = relative_url.set_query_params(sorted(data.items()))

        req = dict(
            method=method,
            relative_url=relative_url,
        )

        if method == 'POST':
            data, files = map(dict, partition(lambda d: hasattr(d[1], 'read'),
                                              data.items()))
            if data:
                req['body'] = urlencode(sorted(data.items()))
            if files:
                req['files'] = files

        return req

    @classmethod
    def prepare_batch(cls, chinups):
        """
        Returns a tuple of (chinups, requests) where requests is a list of
        dicts appropriate for a batch request.
        """
        # Build request dicts for the first 50 chinups, limit imposed by the
        # Facebook API.
        requests = [c.make_request_dict() for c in chinups[:50]]

        # Return the full list of chinups and the possibly shorter list of
        # requests.  Note the requests still match one-to-one with the chinups
        # though, and that's important.
        return chinups, requests


class ChinupBar(object):
    chinup_class = Chinup
    queue_class = ChinupQueue

    def __init__(self, token=None, app_token=None,
                 raise_exceptions=True, prefetch_next_page=True):
        if not app_token:
            app_token = settings.APP_TOKEN
            if not app_token:
                raise ValueError("Either app_token or settings.APP_TOKEN is required.")

        self.app_token = app_token
        self.token = token
        self.raise_exceptions = raise_exceptions
        self.prefetch_next_page = prefetch_next_page

    def _get_queue(self, **kwargs):
        if isinstance(self.queue_class, basestring):
            self.queue_class = get_modattr(self.queue_class)
        return self.queue_class(**kwargs)

    def _get_chinup(self, **kwargs):
        if isinstance(self.chinup_class, basestring):
            self.chinup_class = get_modattr(self.chinup_class)
        return self.chinup_class(**kwargs)

    def _query(self, method, path, data, defer):
        queue = self._get_queue(app_token=self.app_token)
        chinup = self._get_chinup(queue=queue, token=self.token,
                                  method=method, path=path, data=data,
                                  raise_exceptions=self.raise_exceptions,
                                  prefetch_next_page=self.prefetch_next_page)
        chinup = queue.append(chinup)
        if not defer:
            queue.sync(chinup)
            # For non-deferred requests, raise exception immediately rather
            # than waiting for .data to be accessed. This is especially for
            # POST which might not check its response.
            if self.raise_exceptions and chinup.exception:
                raise chinup.exception
        return chinup

    def get(self, path, data=None, defer=True):
        return self._query('GET', path, data, defer)

    def post(self, path, data, defer=False):
        return self._query('POST', path, data, defer)

    def put(self, path, data, defer=False):
        return self._query('PUT', path, data, defer)

    def delete(self, path, data=None, defer=False):
        return self._query('DELETE', path, data, defer)

    def debug_token(self, path='', data=None, defer=True):
        return self._query('DEBUG_TOKEN', path, data, defer)


__all__ = ['Chinup', 'ChinupBar']
