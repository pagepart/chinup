Settings
========

Here's a list of the settings available in chinup and their default values.
To override settings, import the module in your application and set them,
for example::

    import chinup.settings

    chinup.settings.APP_TOKEN = 'NGAUy7KT'
    chinup.settings.DEBUG = True

If you're using Django, you can set them in your Django ``settings.py``::

    CHINUP_APP_TOKEN = 'NGAUy7KT'
    CHINUP_DEBUG = DEBUG  # reflect Django DEBUG setting into chinup

APP_TOKEN
---------

Default: ``None``

An app token is required to make requests with chinup. This is because
chinup *always* makes batch requests, even for a single request, and
Facebook's batch API requires an app token.

If you don't set ``settings.APP_TOKEN`` then you must pass your app token
to ``ChinupBar``, however this will become unwieldy quickly::

    ChinupBar(app_token='NGAUy7KT', token='6Fq7Uy8J').get('me')

CACHE
-----

Default: ``None``

A cache is required to take advantage of etags in batch requests. This
setting can either be a cache object, or a string dotted path to a module
attribute.  For example, using Django's default cache::

    CHINUP_CACHE = 'django.core.cache.cache'

The cache object must support the two methods: ``get_many`` and
``set_many``.

DEBUG
-----

Default: ``False``

Setting this to ``True`` causes chinup to track all the batches, similarly
to Django's tracking of database queries. Then you can verify that batching
is occurring as you expect:

    >>> from chinup.lowlevel import batches
    >>> len(batches)
    3
    >>> [len(b) for b in batches]
    [5, 10, 1]

This shows that you've made three batch requests so far, containing five,
ten, and one request respectively.  You might say to yourself: "That last
one looks suspicious. Can I tune my code to include that request in the
prior batch for better performance, i.e. ``[5, 11]``?"

ETAGS
-----

Default: ``True``

Chinup will cache individual responses within a batch by default, if
``settings.CACHE`` is also set. You can disable this by setting
``ETAGS = False``.

DEBUG_HEADERS
-------------

Default: ``False``

Chinup will omit response headers from the ``repr`` output for a ``Chinup``
by default, since they tend to be lengthy and uninteresting. To include
these headers, set ``DEBUG_HEADERS = True``.

DEBUG_REQUESTS
--------------

Default: ``DEBUG``

Chinup always logs request info, the question is what logging level it will
use.  By default it's ``logging.DEBUG`` but this becomes ``logging.INFO``
if ``DEBUG_REQUESTS`` is ``True``.

TESTING
-------

Default: ``False``

This has the same effect as setting ``DEBUG``, meaning that it causes
``chinup.lowlevel.batches`` to be tracked. Normally you don't set this
yourself, rather it's set by the provided ``ChinupTestMixin``. Then you can
use ``assertBatches`` to make sure that changes to your code don't cause an
unwelcome change in the number of batches and requests.
