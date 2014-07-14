Advanced
========

Paging
------

Chinup supports transparent or explicit paging of Facebook data. To access
all the response data, paging transparently, iterate over the Chinup
object::

    friends = ChinupBar(token='6Fq7Uy8J').get('me/friends')
    for friend in friends:
        print friend['name']

This will fetch additional pages as necessary to iterate over the entire
list of friends. Listifying will also fetch all the pages::

    friends = ChinupBar(token='6Fq7Uy8J').get('me/friends')
    friends = list(friends)

Alternatively you can control paging explicitly by calling the
``next_page`` method.  In that case, you should iterate on ``data``
to avoid automatic paging::

    friends = ChinupBar(token='6Fq7Uy8J').get('me/friends')
    while friends:
        for friend in friends.data:
            print friend['name']
        friends = friends.next_page()

ETags
-----

The Facebook batch API supports ETags in requests and responses. See
https://developers.facebook.com/docs/reference/ads-api/batch-requests/#etags

Chinup supports ETags transparently if you provide a suitable
``settings.CACHE``, then chinup will automatically convert 304 responses to
the previously cached 200 response.

Inter-request dependencies
--------------------------

Chinup does not yet support inter-request dependencies with JSONpath.
This is on the radar though!  See
https://developers.facebook.com/docs/graph-api/making-multiple-requests/#operations

raise_exceptions=False
----------------------

If chinup encounters an error retrieving a response from the Facebook
Graph, the ``Chinup`` object will raise its own exception whenever your
code attempts to access the response data.  For large batch operations
where you're expecting errors, you can avoid the exception by setting
``raise_exceptions=False``::

    chinups = [ChinupBar(user=u, raise_exceptions=False).get('me')
               for u in User.objects.all()]
    for c in chinups:
        print "%s: %r" % (c.user, c.data or c.exception)

The above example uses ``raise_exceptions=False`` to handle users that
don't have associated tokens, or maybe their tokens have expired.  The
``data`` attribute for those chinups will be ``None`` and will not raise an
exception when accessed.

Testing
-------

Chinup provides a mixin for Python ``unittest``. The mixin clears state
prior to each test, and provides ``assertBatches`` to make sure your code
changes don't adversely affect the batching of requests to Facebook.  For
example::

    from django.test import TestCase
    from chinup.testing import ChinupTestMixin

    from app import something

    class MyTestCase(ChinupTestMixin, TestCase):
        
        def test_something(self):
            something()

            # Calling something() should have resulted in two batches with
            # a total of 30 requests.
            self.assertBatches(2, 30)

Subclassing
-----------

While the ``Chinup`` and ``ChinupBar`` classes can be used out of the box,
they're amenable to subclassing to support object and token lookup
according to the specifics of your project. The most prominent example is
the built-in support for django-allauth_. If the allauth module can be
imported, then ``ChinupBar`` will accept a ``user`` parameter rather than
requiring a ``token`` parameter.

Here's another example, which layers on support for Facebook page tokens
from a separate table. Be sure to set ``ChinupBar.chinup_class`` to your
subclass, as shown below.

::

    import chinup
    from chinup.exceptions import ChinupError, MissingToken
    from myapp.models import Page


    class NoSuchPage(ChinupError):
        pass


    class Chinup(chinup.Chinup):

        def __init__(self, **kwargs):
            self.page = kwargs.pop('page', None)

            # Make sure there's only one token provider on this Chinup:
            # page or user, not both.
            assert not (self.page and kwargs.get('user'))

            super(Chinup, self).__init__(**kwargs)

        @classmethod
        def prepare_batch(cls, chinups):
            """
            Populates page tokens into chinups. This also immediately
            "completes" any chinups which require a token that isn't
            available, by setting chinup.exception.
            """
            cls._fetch_pages(chinups)
            cls._fetch_page_tokens(chinups)

            # Weed out any chinups that didn't pass token stage.
            chinups = [c for c in chinups if not c.completed]

            return super(Chinup, cls).prepare_batch(chinups)

        @classmethod
        def _fetch_pages(cls, chinups):
            """
            Replaces .page=PK with .page=OBJ for the chinups in the list.
            If the PK can't be found, then sets NoSuchPage to be raised
            when the chinup data is accessed.
            """
            chinups = [c for c in chinups if not c.completed and not c.token
                       and isinstance(c.page, basestring)]
            if chinups:
                pages = Page.objects.filter(pk__in=set(c.page for c in chinups))
                pages = {page.pk: page for page in pages}

                for c in chinups:
                    page = pages.get(c.page)
                    if page:
                        c.page = page
                    else:
                        c.exception = NoSuchPage("No page with pk=%r" % c.page)

        @classmethod
        def _fetch_page_tokens(cls, chinups):
            """
            Sets .token for the chinups in the list that have .page set.
            If a token isn't available for the given page, then sets
            MissingToken to be raised when the chinup data is accessed.
            """
            chinups = [c for c in chinups if not c.completed and not c.token
                       and c.page]
            if chinups:
                page_tokens = PageToken.objects.filter(
                    account__page_id__in=set(c.page.pk for c in chinups),
                )
                page_tokens = page_tokens.select_related('account')
                tokens = {pt.account.page_id: pt.token for pt in page_tokens}

                for c in chinups:
                    token = tokens.get(c.page.pk)
                    if token:
                        c.token = token
                    else:
                        c.exception = MissingToken("No token for %r" % c.page)


    class ChinupBar(chinup.ChinupBar):
        chinup_class = Chinup

        def __init__(self, **kwargs):
            self.page = kwargs.pop('page', None)

            # Make sure there's only one token provider on this ChinupBar:
            # page or user, not both.
            assert not (self.page and kwargs.get('user'))

            super(ChinupBar, self).__init__(**kwargs)

        def _get_chinup(self, **kwargs):
            return super(ChinupBar, self)._get_chinup(
                page=self.page,
                **kwargs)

.. _django-allauth: http://www.intenct.nl/projects/django-allauth/
