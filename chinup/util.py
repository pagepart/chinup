from __future__ import absolute_import, unicode_literals

import hmac
import hashlib
import json
import logging
import os
import stat
import sys


logger = logging.getLogger(__name__)


def partition(cond, seq, parts=2):
    """
    Partition function from Erik Wilsher on Ned's blog at
    http://nedbatchelder.com/blog/200607/partition_for_python.html
    but with cond first, to match filter, map, etc.
    """
    res = [[] for i in range(parts)]
    for e in seq:
        res[int(cond(e))].append(e)
    return res


def get_modattr(s):
    assert isinstance(s, basestring) and '.' in s
    pkg, attr = s.rsplit('.', 1)
    __import__(pkg)
    return getattr(sys.modules[pkg], attr)


def dev_inode(f):
    """
    Returns the (dev, inode) pair suitable for uniquely identifying a file,
    just as os.path.samefile() would do. This includes a fallback for
    fileno/fstat failure, since that happens on closed files, remote files,
    etc.
    """
    try:
        st = os.fstat(f.fileno())
        return st[stat.ST_DEV], st[stat.ST_INO]
    except Exception as e:
        logger.debug("%s in fstat/fileno for %r",
                     e.__class__.__name__, f)
    return -1, id(f)


def as_json(data):
    """
    Consistent JSON dumping, with key sorting for test stability.
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'))


def get_proof(key, msg):
    """
    Returns appsecret_proof, see
    https://developers.facebook.com/docs/graph-api/securing-requests
    """
    if isinstance(key, unicode):
        key = key.encode('utf-8')
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    h = hmac.new(key, msg, hashlib.sha256)
    return h.hexdigest()
