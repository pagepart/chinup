from __future__ import absolute_import, unicode_literals

import sys


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
