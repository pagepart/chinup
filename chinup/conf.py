from __future__ import absolute_import, unicode_literals

from .util import get_modattr


class Settings(object):

    def __init__(self, resolvable_settings=None):
        self._sources = []
        self._resolved = {}
        self._resolvable_settings = resolvable_settings or []

    def __getattr__(self, name):
        for s in reversed(self._sources):
            try:
                value = getattr(s, name)
            except AttributeError:
                pass
            else:
                return self._resolve(name, value)
        raise AttributeError("chinup setting %r not found" % name)

    def _resolve(self, name, value):
        if name in self._resolvable_settings and isinstance(value, basestring):
            try:
                value = self._resolved[value]
            except KeyError:
                value = self._resolved[value] = get_modattr(value)
        return value


class PrefixedSettingsSource(object):

    def __init__(self, data, prefix):
        self._data = data
        self._prefix = prefix

    def __getattr__(self, name):
        return getattr(self._data, self._prefix + name)


settings = Settings(resolvable_settings=[
    'CACHE',
])


from . import settings as chinup_settings
settings._sources.append(chinup_settings)


try:
    from django.conf import settings as django_settings
except ImportError:
    pass
else:
    settings._sources.append(PrefixedSettingsSource(django_settings, 'CHINUP_'))
