try:
    from .allauth import *
except ImportError:
    from .chinup import *

from .exceptions import *
