from __future__ import absolute_import, unicode_literals

try:
    from .allauth import *
except ImportError:
    from .chinup import *
from .queue import *
from .exceptions import *


__version__ = '0.2.4'


# Configure logging to avoid warning.
# https://docs.python.org/2/howto/logging.html#configuring-logging-for-a-library
import logging
if hasattr(logging, 'NullHandler'):
    logging.getLogger('chinup').addHandler(logging.NullHandler())
