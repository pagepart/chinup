from __future__ import absolute_import, unicode_literals

import sys

from . import settings


def get_cache():
    if not hasattr(settings, '_CACHE'):
        settings._CACHE = None
        if isinstance(settings.CACHE, basestring):
            pkg, attr = settings.CACHE.rsplit('.', 1)
            __import__(pkg)
            settings._CACHE = getattr(sys.modules[pkg], attr)
    return settings._CACHE
