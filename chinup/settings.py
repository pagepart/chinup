from __future__ import absolute_import, unicode_literals


APP_TOKEN = None
DEBUG = False
DEBUG_REQUESTS = DEBUG
DEBUG_HEADERS = False
TESTING = False
ETAGS = True
CACHE = None


try:
    from django.conf import settings
except ImportError:
    pass
else:
    for name in dir(settings):
        if name.startswith('CHINUP_'):
            locals()[name[7:]] = getattr(settings, name)


__all__ = [name for name in locals() if name.isupper()]
