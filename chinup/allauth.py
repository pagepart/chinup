from __future__ import absolute_import, unicode_literals

from allauth.socialaccount.models import SocialToken
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.db.models import Q

from . import chinup, exceptions


class NoSuchUser(exceptions.ChinupError):
    pass

exceptions.NoSuchUser = NoSuchUser


class MissingToken(exceptions.ChinupError):
    pass

exceptions.MissingToken = MissingToken


class Chinup(chinup.Chinup):

    def __init__(self, **kwargs):
        self.user = kwargs.pop('user', None)
        super(Chinup, self).__init__(**kwargs)

    def __unicode__(self, extra=''):
        extra = '{}user={}'.format(extra and extra + ' ', self.user)
        return super(Chinup, self).__unicode__(extra=extra)

    def __getstate__(self):
        return dict(super(Chinup, self).__getstate__(),
                    user=getattr(self.user, 'pk', self.user))

    @classmethod
    def prepare_batch(cls, chinups):
        # Populate user tokens into chinups. This also immediately "completes"
        # any chinups which require a token that isn't available, by setting
        # chinup.exception.
        cls._fetch_users(chinups)
        cls._fetch_user_tokens(chinups)

        # Weed out any chinups that didn't pass token stage.
        chinups = [c for c in chinups if not c.completed]

        return super(Chinup, cls).prepare_batch(chinups)

    @classmethod
    def _fetch_users(cls, chinups):
        chinups = [c for c in chinups if not c.completed and not c.token
                   and isinstance(c.user, basestring)]
        if chinups:
            users = cls._users_dict(chinups)
            for c in chinups:
                user = users.get(c.user)
                if user:
                    c.user = user
                else:
                    c.exception = NoSuchUser("No user %r" % c.user)

    @classmethod
    def _users_dict(cls, chinups):
        User = get_user_model()
        db_users = User.objects.filter(
            Q(pk__in=set(c.user for c in chinups if isinstance(c.user, int))) |
            Q(username__in=set(c.user for c in chinups if isinstance(c.user, basestring))))
        users = {u.pk: u for u in db_users}
        users.update({u.username: u for u in db_users})
        return users

    @classmethod
    def _fetch_user_tokens(cls, chinups):
        chinups = [c for c in chinups if not c.completed and not c.token
                   and c.user]
        if chinups:
            social_tokens = cls._social_token_queryset(chinups)
            social_tokens = social_tokens.select_related('account',
                                                         'account__user')
            assert (len(set(st.account.user_id for st in social_tokens)) ==
                    len(social_tokens))
            tokens = {st.account.user_id: st.token for st in social_tokens}

            for c in chinups:
                token = tokens.get(c.user.pk)
                if token:
                    c.token = token
                else:
                    c.exception = MissingToken("No token for %r" % c.user)

    @classmethod
    def _social_token_queryset(cls, chinups, **kwargs):
        site_id = getattr(django_settings, 'SITE_ID', None)
        if site_id:
            kwargs.setdefault('app__sites__id', site_id)
        return SocialToken.objects.filter(
            account__user__in=set(c.user for c in chinups),
            **kwargs)


class ChinupBar(chinup.ChinupBar):
    chinup_class = Chinup

    def __init__(self, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ChinupBar, self).__init__(**kwargs)

    def _get_chinup(self, **kwargs):
        return super(ChinupBar, self)._get_chinup(
            user=self.user, **kwargs)


__all__ = ['Chinup', 'ChinupBar', 'NoSuchUser', 'MissingToken']
