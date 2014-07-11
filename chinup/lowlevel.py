from __future__ import absolute_import, unicode_literals

from decimal import Decimal
import hashlib
import imghdr
import json
import logging
import mimetypes
import os
import sys

import requests
from requests.utils import guess_filename

from . import settings
from .cache import get_cache
from .exceptions import OAuthError, TransportError, FacebookError


logger = logging.getLogger(__name__)


batches = []

def batch_request(app_token, reqs, url='https://graph.facebook.com'):
    """
    Runs a batch request to the Facebook API.
    """
    required_keys = set(['method', 'relative_url'])
    assert all(required_keys <= set(r) for r in reqs)

    # Split out binary attachments.
    # https://developers.facebook.com/docs/graph-api/making-multiple-requests/#binary
    #
    # The batch API doesn't provide any way to name the file upload fields.
    # For example, normal upload to me/photos uses the "source" parameter
    # to include a file; batch upload to me/photos specifies
    # "attached_files."  We hope this also works for other upload endpoints
    # such as ad creation.  It will break down for any endpoint that
    # requires uploading more than one file simultaneously.
    files = {}
    for i, req in enumerate(reqs, 1):
        if 'files' in req:
            reqfiles = {'file{}-{}'.format(i, j): f
                        for j, f in enumerate(req['files'].values())}
            assert all(f not in files for f in reqfiles)
            files.update(reqfiles)
            req['attached_files'] = ','.join(reqfiles)
            del req['files']

    # Upgrade files to tuples with content-type.
    files = {k: file_tuple(f, k) for k, f in files.items()}

    # Add etags headers.
    if settings.ETAGS:
        edicts = add_etags(reqs, app_token)

    # Similar to django.db.connection.queries, save batched requests in
    # debug mode for inspection.
    if settings.DEBUG or settings.TESTING:
        batches.append(reqs)

    # Post the batch request. Always include headers, for
    #  1. 302 location header on biz picture image,
    #  2. etags support,
    #  3. debugging.
    data = dict(access_token=app_token,
                batch=json.dumps(reqs),
                include_headers='true')
    try:
        r = requests.post(url, data=data, files=files)
    except requests.RequestException as e:
        raise TransportError(e)

    # Attempt to parse before checking HTTP status, because
    # parse_fb_response() will raise an exception for Facebook enumerated
    # error responses.
    resps = parse_fb_response(r)
    if r.status_code != 200:
        raise FacebookError("HTTP {}: {}".format(r.status_code, resps))
    if not isinstance(resps, list):
        raise FacebookError(resps)

    # Handle etags in responses.
    if settings.ETAGS:
        resps = handle_etags(resps, edicts)

    # Check for a timeout, unambiguously represented by null in the JSON,
    # or None when decoded.
    # https://developers.facebook.com/docs/graph-api/making-multiple-requests/#timeouts
    timed_out = sum(1 for r in resps if r is None)
    if timed_out:
        logger.warning("Timed out %d in batch of %d requests.", timed_out, len(reqs))

    return resps


def parse_fb_response(response):
    data = response.content.decode('utf-8')
    try:
        data = json.loads(data, parse_float=Decimal)
    except ValueError:
        pass
    else:
        exc = parse_fb_exception(data)
        if exc:
            raise exc
    return data


def parse_fb_exception(data):
    if data is False:
        return FacebookError("Facebook returned false")

    if isinstance(data, dict) and 'error' in data:
        error = data['error']
        if error.get('type') == 'OAuthException':
            eclass = OAuthError
        else:
            eclass = FacebookError
        return eclass(error.get('message'), error.get('code'))


def file_tuple(f, default_name=None, image=True):
    """
    Returns a tuple suitable for requests file upload, particularly to enable
    Facebook APIs that require the content-type to be set.
    """
    # Same variable names as in RequestEncodingMixin._encode_files().
    fn, fp, ft, fh = None, None, None, None

    if isinstance(f, (tuple, list)):
        # Assign as many as provided.
        try:
            fn = f[0]
            fp = f[1]
            ft = f[2]
            fh = f[3]
        except IndexError:
            pass
    else:
        # As in requests, bare value is file pointer or content.
        fp = f

    if not fn:
        fn = guess_filename(fp) or default_name

    # Try to get content-type from filename first.
    if not ft and fn:
        ext = os.path.splitext(fn)[1].lower()
        ft = mimetypes.types_map.get(ext)

    # Fall back to detecting the image type from the header.
    if not ft and image:
        ext = None
        if isinstance(fp, basestring):
            ext = imghdr.what(None, fp[:32])
        elif callable(getattr(fp, 'seek', None)):
            try:
                ext = imghdr.what(fp)
            except IOError:  # unseekable file
                pass
        if ext:
            ft = mimetypes.types_map.get(ext)

    return fn, fp, ft, fh


def add_etags(requests, app_token):
    """
    Returns a list of dicts like this:

      edicts = [ { request, key, responses },
                 { request, key, responses },
               ]

    where responses is an entry from cache with this structure:

      [ (etag, response),
        (etag, response),
      ]

    The list of dicts (edicts) is passed back to caller, so it can be reused by
    handle_etags below.
    """
    cache = get_cache()
    edicts = [dict(request=r, key=etags_cache_key(r, app_token))
              for r in requests]
    if cache:
        responses = cache.get_many([e['key'] for e in edicts])
    else:
        logger.warning("Chinup ETAGS=True but CACHE=%r", cache)
        responses = {}
    edicts = [dict(e, responses=responses.get(e['key'], []))
              for e in edicts]

    for edict in edicts:
        if edict['responses']:
            headers = edict['request'].setdefault('headers', [])
            assert all(not h.lower().startswith('if-none-match:')
                       for h in headers)
            headers.append("If-None-Match: {}".format(
                ', '.join(e for e, r in edict['responses'])))

    return edicts


def handle_etags(responses, edicts):
    """
    Restores cached responses, and saves new etagged responses to cache.
    Returns the new list of responses.
    """
    # We must have at least as many edicts as responses, otherwise
    # new_responses will be truncated.
    assert len(edicts) >= len(responses)

    new_responses = []
    to_cache = {}

    for response, edict in zip(responses, edicts):
        if isinstance(response, dict) and 'headers' in response:
            # Check for an etag in the response (whether 304 or 200).
            etag = next((h['value'] for h in response['headers']
                         if h['name'].lower() == 'etag'), None)

            # Check for a 304 response, look for matching etag.
            if response['code'] == 304:
                if etag:
                    assert edict['responses']
                    response = next(r for e, r in edict['responses'] if e == etag)
                else:
                    assert len(edict['responses']) == 1
                    etag, response = edict['responses'][0]

                logger.debug("Got 304 etag=%s, replacing with %s",
                             etag, response['code'])

            # Promote this etag to front of cache list for this request.
            if etag:
                resps = [(etag, response)]
                resps.extend((e, r) for e, r in edict['responses'] if e != etag)
                # Facebook should return an ETag header with a 304
                # response, but it does not. This means we can't actually cache
                # more than one response per request at a time, which is
                # annoying but probably fine.
                resps = resps[:1]
                to_cache[edict['key']] = resps

        new_responses.append(response)

    # Update cached etags.
    cache = get_cache()
    if cache:
        cache.set_many(to_cache, timeout=86400)  # one day
    else:
        logger.warning("Chinup ETAGS=True but CACHE=%r", cache)

    assert len(new_responses) == len(responses)
    return new_responses


def etags_cache_key(request, app_token):
    assert all(isinstance(k, basestring) for k in request.keys())
    assert all(isinstance(v, basestring) for v in request.values())
    m = hashlib.md5(repr(sorted(request.items())))
    m.update(app_token)
    key = 'chinup.etags.' + m.hexdigest()
    assert len(key) <= 250
    return key
