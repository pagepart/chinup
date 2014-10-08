from __future__ import absolute_import, unicode_literals


class FacebookErrorMixin(object):
    """Exception for Facebook enumerated errors."""

    def __init__(self, message=None):
        self.error = None
        self.code = None
        self.subcode = None

        if message is False:
            message = "Graph API returned false"

        elif isinstance(message, dict):
            self.error = message
            self.code = self.error.get('code')
            self.subcode = self.error.get('error_subcode')
            user_message = self.error.get('error_user_message') or ''
            user_title = self.error.get('error_user_title') or ''
            message = self.error.get('message')

            if user_title == user_message:
                user_title = ''
            elif user_title and user_message:
                user_title += ': '
            if user_title or user_message:
                message = '{} ({}{})'.format(message, user_title, user_message)

            if self.code and self.subcode:
                message = '[{}.{}] {}'.format(self.code, self.subcode, message)
            elif self.code:
                message = '[{}] {}'.format(self.code, message)

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
