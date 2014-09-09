from __future__ import absolute_import, unicode_literals

import sys

from .util import get_modattr
from . import settings


def get_cache():
    if not hasattr(settings, '_CACHE'):
        settings._CACHE = None
        if isinstance(settings.CACHE, basestring):
            settings._CACHE = get_modattr(settings.CACHE)
    return settings._CACHE
