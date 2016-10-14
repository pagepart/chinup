from __future__ import absolute_import, unicode_literals

import collections
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
from .util import partition, get_modattr, dev_inode, as_json, get_proof
from .conf import settings


logger = logging.getLogger(__name__)


class Chinup(collections.Mapping):
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

    def __init__(self, queue, method, path, data, **kwargs):
        required = ['token', 'raise_exceptions', 'callback',
                    'prefetch_next_page', 'summary_info',
                    'migrations', 'app_secret']
        missing = set(required) - set(kwargs)
        extra = set(kwargs) - set(required)
        if missing or extra:
            raise ValueError("Wrong kwargs: missing={!r}, extra={!r}".format(
                list(missing), list(extra)))

        self.queue = queue
        self.request = dict(method=method, path=path, data=data)
        self._response = None
        self._exception = None
        self._next_page = None
        self.__dict__.update(kwargs)

        # and put it on the queue...
        self.queue.append(self)

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

    def sync(self):
        """
        Forces a sync of this chinup, as accessing .data would do.
        This is especially for chinups with a callback, where the
        caller wants to sync for the sake of triggering the callback.
        """
        self._sync()
        self._maybe_raise_exception()

    @property
    def response(self):
        self._sync()
        return self._response

    @response.setter
    def response(self, response):
        self._set_response(response)

    def _set_response(self, response):
        self._response = response

        # Decode and promote response body. The body can be None if the HTTP
        # status code isn't 200, for example 302 with a Location header.
        if isinstance(response, dict) and response.get('body') is not None:
            try:
                body = json.loads(response['body'])
            except ValueError as e:
                if not self._exception:
                    self.exception = e
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
            self.exception = parse_fb_exception(response)

        # If this chinup has an associated callback, call it now. This allows
        # the caller to chain chinups, for example an async ads report. Don't
        # use this if you're not sure you need it.
        if self.callback:
            try:
                self.callback(self)
            except Exception as e:
                if not self._exception:
                    self.exception = e

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
        if value:
            self._exception.chinup = self

    def _maybe_raise_exception(self):
        if self.raise_exceptions and self.exception:
            logger.debug("Raising %s for %r", self.exception.__class__.__name__, self)
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

        defaults = dict(
            queue=self.queue,
            method=self.request['method'],
            path=URL(next_link).with_scheme('').with_netloc('')[1:],
            token=None,
            app_secret=None,
            data=None,  # all params are in next_link
            raise_exceptions=self.raise_exceptions,
            callback=None,  # only on first page
            prefetch_next_page=self.prefetch_next_page,
            summary_info=False,  # don't force after first page
            migrations=self.migrations,
        )

        # There's no mention of applying appsecret_proof to paging links in the
        # Facebook documentation, but if we have a secret and the token
        # matches, then let's apply it.
        next_url = URL(next_link)
        if (self.app_secret and
                'appsecret_proof' not in next_url.query_dict and
                next_url.query_dict.get('access_token') == self.token):
            defaults.update(
                token=self.token,
                app_secret=self.app_secret,
            )

        kwargs = dict(defaults, **kwargs)
        return self.__class__(**kwargs)

    def next_page(self):
        """
        Returns the chinup corresponding to the next page, or None if
        il n'y en a pas.
        """
        self.fetch_next_page()
        return self._next_page

    def __iter__(self):
        """
        For paged list-based responses, yield successive records from
        self.data, advancing through paged data automatically.

        For non-paged dict-based responses, yield keys for collections.Mapping.
        """
        paging = not isinstance(self.data, dict)
        chinup = self
        while chinup:  # will be None on last page
            if not isinstance(chinup.data, (dict, list)):
                if not self.exception:
                    self.exception = PagingError("Unexpected chinup.data while paging")
                    self.exception.chinup = chinup
                self._maybe_raise_exception()
                break
            for d in chinup.data:
                yield d
            if not paging:
                break
            chinup = chinup.next_page()

    def __len__(self):
        """
        Returns the number of records in data. Tries to use summary if
        available, otherwise returns the length of data in this chinup rather
        than all pages, to avoid infinite recursion because Python calls
        len(obj) as a first step to list(obj).
        """
        if isinstance(self.response, dict):
            try:
                count = self.response['summary']['total_count']
                if isinstance(count, int):
                    return count
            except Exception:
                pass
            if self.summary_info:
                logger.debug("summary_info=%r but response['summary']=%r",
                             self.summary_info, self.response.get('summary'))

        # If self.raise_exceptions is False, then self.data might be None.
        # Don't accidentally raise an exception here with len(None).
        return len(self.data or [])

    def __nonzero__(self):
        # Prevent truth value testing from calling len(self).
        return True

    def __getitem__(self, key):
        if isinstance(key, int) and isinstance(self.data, list):
            if key < len(self.data):
                return self.data[key]
            else:
                # Invoke paging
                return list(self)[key]
        return self.data[key]

    def __eq__(self, other):
        """
        Returns True if requests match. If both chinups are complete, then also
        compares their completion characteristics (response and exception).
        """
        if self.__class__ != other.__class__:
            if isinstance(other, Chinup):
                logger.debug("__eq__ class mismatch")
            return False

        req, oreq = self._make_eq_dict(), other._make_eq_dict()
        if req != oreq:
            #logger.debug("__eq__ req mismatch")
            return False

        if self.raise_exceptions != other.raise_exceptions:
            logger.debug("__eq__ raise_exceptions mismatch")
            return False

        if self.completed != other.completed:
            logger.debug("__eq__ completed mismatch")
            return False

        return True

    def _make_eq_dict(self):
        """
        Returns a modified request dict suitable for __eq__ and __hash__.
        """
        req = self.make_request_dict()
        if 'files' in req:
            # Replace {name: file} with {name: (dev, inode)}
            files = {k: dev_inode(f) for k, f in req['files'].items()}
            # and convert to a sorted tuple.
            req['files'] = tuple(sorted(files.items()))
        return req

    def __hash__(self):
        eq_dict = self._make_eq_dict()
        return hash(tuple(sorted(eq_dict.items())))

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
        self.queue.append(self)

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
            if not self.token:
                raise ValueError("can't debug_token without a token")
            method = 'GET'
            path = 'debug_token'
            if self.api_version:
                path = '{}/{}'.format(self.api_version, path)
            relative_url = URL(path).set_query_params(
                input_token=self.token)

        elif self.token:
            relative_url = relative_url.set_query_params(
                access_token=self.token)
            if self.app_secret:
                relative_url = relative_url.set_query_params(
                    appsecret_proof=get_proof(key=self.app_secret,
                                              msg=self.token))

        if method != 'POST':
            relative_url = relative_url.set_query_params(
                self._encode_data(data))

        if self.summary_info:
            relative_url = relative_url.set_query_params(
                summary='true')

        if self.migrations:
            relative_url = relative_url.set_query_params(
                migrations_override=as_json(self.migrations))

        if settings.RELATIVE_URL_HOOK:
            relative_url = settings.RELATIVE_URL_HOOK(relative_url)

        req = dict(
            method=method,
            relative_url=relative_url,
        )

        if method == 'POST':
            data, files = map(dict, partition(lambda d: hasattr(d[1], 'read'),
                                              data.items()))
            if data:
                req['body'] = urlencode(self._encode_data(data))
            if files:
                req['files'] = files

        return req

    @classmethod
    def _encode_data(cls, data):
        """
        Returns data dict as a list of (key, value) tuples.
        List or dict values will be JSON encoded.
        """
        items = []

        for k, v in sorted(data.items()):
            if isinstance(v, list):
                v = as_json(v)
            elif callable(getattr(v, 'items', None)):
                v = as_json(v)
            items.append((k, v))

        return items

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

    def __init__(self, token=None, app_token=None, **kwargs):
        if not app_token:
            app_token = settings.APP_TOKEN
            if not app_token:
                raise ValueError("Either app_token or settings.APP_TOKEN is required.")

        defaults = dict(
            api_version=settings.API_VERSION,
            raise_exceptions=True,
            prefetch_next_page=True,
            summary_info=settings.SUMMARY_INFO,
            migrations=settings.MIGRATIONS,
            app_secret=settings.APP_SECRET,
        )
        extra = set(kwargs) - set(defaults)
        if extra:
            raise ValueError("Extra kwargs: {!r}".format(list(extra)))
        defaults.update(kwargs)

        self.token = token
        self.app_token = app_token
        self.__dict__.update(defaults)

    def _get_queue(self, **kwargs):
        if isinstance(self.queue_class, basestring):
            self.queue_class = get_modattr(self.queue_class)
        return self.queue_class(**kwargs)

    def _get_chinup(self, **kwargs):
        if isinstance(self.chinup_class, basestring):
            self.chinup_class = get_modattr(self.chinup_class)
        return self.chinup_class(**kwargs)

    def _query(self, method, path, data, defer, callback):
        if self.api_version:
            path = '{}/{}'.format(self.api_version, path.lstrip('/'))

        queue = self._get_queue(app_token=self.app_token,
                                app_secret=self.app_secret)
        chinup = self._get_chinup(queue=queue, token=self.token,
                                  app_secret=self.app_secret,
                                  method=method, path=path, data=data,
                                  raise_exceptions=self.raise_exceptions,
                                  callback=callback,
                                  prefetch_next_page=self.prefetch_next_page,
                                  summary_info=self.summary_info,
                                  migrations=self.migrations)

        if not defer:
            queue.sync(chinup)
            # For non-deferred requests, raise exception immediately rather
            # than waiting for .data to be accessed. This is especially for
            # POST which might not check its response.
            if self.raise_exceptions and chinup.exception:
                raise chinup.exception

        return chinup

    def get(self, path, data=None, defer=True, callback=None):
        return self._query('GET', path, data, defer, callback)

    def post(self, path, data, defer=False, callback=None):
        return self._query('POST', path, data, defer, callback)

    def put(self, path, data, defer=False, callback=None):
        return self._query('PUT', path, data, defer, callback)

    def delete(self, path, data=None, defer=False, callback=None):
        return self._query('DELETE', path, data, defer, callback)

    def debug_token(self, path='', data=None, defer=True):
        return self._query('DEBUG_TOKEN', path, data, defer, None)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__.update(d)


try:
    from yaml import YAMLObject
except ImportError:
    pass
else:
    class GetSetStateYAMLMixin(object):

        @classmethod
        def to_yaml(cls, dumper, data):
            d = data.__getstate__()
            data.__dict__.update(d)
            return super(GetSetStateYAMLMixin, cls).to_yaml(dumper, data)

        @classmethod
        def from_yaml(cls, loader, node):
            data = super(GetSetStateYAMLMixin, cls).from_yaml(loader, node)
            data.__setstate__(data.__dict__)
            return data

    class ChinupYAMLObject(GetSetStateYAMLMixin, YAMLObject):
        yaml_tag = '!Chinup'

    class ChinupBarYAMLObject(GetSetStateYAMLMixin, YAMLObject):
        yaml_tag = '!ChinupBar'


__all__ = ['Chinup', 'ChinupBar']
