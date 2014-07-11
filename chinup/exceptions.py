from __future__ import absolute_import, unicode_literals


class ChinupError(Exception):
    """Base class for exceptions raised by chinup."""


class FacebookError(ChinupError):
    """Exception for Facebook enumerated errors."""
    def __init__(self, message=None, code=None):
        self.code = code
        if code is not None:
            message = '[{}] {}'.format(code, message)
        super(FacebookError, self).__init__(message)


class OAuthError(FacebookError):
    """Exception for Facebook errors specifically related to OAuth."""


class TransportError(ChinupError):
    """Exception for transport errors."""
    def __init__(self, message=None):
        self.e = None
        if isinstance(message, Exception):
            self.e = message
            message = '{}: {}'.format(message.__class__.__name__, message)
        super(TransportError, self).__init__(message)


class QueueTimedOut(ChinupError):
    pass


class PagingError(ChinupError):
    pass


class ChinupCanceled(ChinupError):
    pass
