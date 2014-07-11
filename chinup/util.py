from __future__ import absolute_import, unicode_literals


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
