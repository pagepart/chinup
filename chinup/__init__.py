try:
    from .allauth import *
except ImportError:
    from .chinup import *

from .exceptions import *


__version__ = '0.1'
