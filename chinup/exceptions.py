from __future__ import absolute_import, unicode_literals


class FacebookErrorMixin(object):
    """Exception for Facebook enumerated errors."""

    def __init__(self, message=None, code=None):
        self.code = code
        if code is not None:
            message = '[{}] {}'.format(code, message)
        super(FacebookErrorMixin, self).__init__(message)


class WrappedExceptionMixin(object):
    """Exception possibly wrapping another exception."""

    def __init__(self, *args, **kwargs):
        if 'message' in kwargs:
            message = kwargs['message']
        elif args:
            message, args = args[0], args[1:]
        else:
            message = None

        self.e = None
        if isinstance(message, Exception):
            self.e = message
            message = '{}: {}'.format(message.__class__.__name__, message)

        if message is not None:
            args = (message,) + args

        super(WrappedExceptionMixin, self).__init__(*args, **kwargs)


class BatchError(Exception):
    """Base class for chinup exception in low-level batch processing."""


class TransportError(WrappedExceptionMixin, BatchError):
    """Transport error in low-level batch processing."""


class BatchFacebookError(FacebookErrorMixin, BatchError):
    """Facebook API error during batch processing."""


class BatchOAuthError(BatchFacebookError):
    """OAuth error during batch processing."""


class ChinupError(Exception):
    """Base class for chinup exception in an individual response."""
    _lowlevel_class = BatchError


class FacebookError(FacebookErrorMixin, ChinupError):
    """Facebook API error in an individual Chinup"""
    _lowlevel_class = BatchFacebookError


class OAuthError(FacebookError):
    """OAuth error in an individual Chinup"""
    _lowlevel_class = BatchOAuthError


class QueueTimedOut(ChinupError):
    pass


class PagingError(ChinupError):
    pass


class ChinupCanceled(ChinupError):
    pass
