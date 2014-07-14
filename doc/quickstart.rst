Quickstart
==========

First, install chinup:

.. code:: bash

    pip install chinup

Set your app token in chinup settings. Do this in your own
application code, by importing the ``chinup.settings`` module::

    >>> import chinup.settings
    >>> chinup.settings.APP_TOKEN = 'NGAUy7KT'

Now make a request::

    >>> from chinup import ChinupBar
    >>> c = ChinupBar().get('facebook')
    >>> c
    <Chinup id=140416098416080 GET facebook data=None response=None >

At this point you have a request on the queue, but it hasn't actually
fetched from Facebook. It will be fetched as soon as you access the data::

    >>> c.data
    {u'about': u'The Facebook Page celebrates how our friends inspire us, support us, and help us discover the world when we connect.',
     u'can_post': False,
     u'category': u'Product/service',
     u'checkins': 348,
     u'cover': {u'cover_id': u'10152883780951729',
      u'offset_x': 0,
      u'offset_y': 45,
      u'source': u'https://scontent-b.xx.fbcdn.net/hphotos-xfp1/t31.0-8/q71/s720x720/10497021_10152883780951729_5073009835048541764_o.jpg'},
     u'founded': u'February 4, 2004',
     u'has_added_app': False,
     u'id': u'20531316728',
     u'is_community_page': False,
     u'is_published': True,
     u'likes': 154837767,
     u'link': u'https://www.facebook.com/facebook',
     u'mission': u'Founded in 2004, Facebook\u2019s mission is to give people the power to share and make the world more open and connected. People use Facebook to stay connected with friends and family, to discover what\u2019s going on in the world, and to share and express what matters to them.',
     u'name': u'Facebook',
     u'parking': {u'lot': 0, u'street': 0, u'valet': 0},
     u'talking_about_count': 2796719,
     u'username': u'facebook',
     u'website': u'http://www.facebook.com',
     u'were_here_count': 0}

As a shortcut, you can use keyed access on the chinup directly, rather than
through the ``data`` attribute::

    >>> c['name']
    u'Facebook'

App tokens have very limited functionality on the Graph API. Most of the
time you'll need either a user token or a page token. You can pass that
token to ``ChinupBar``::

    >>> ChinupBar(token='6Fq7Uy8J').get('me')['name']
    u'Aron Griffis'

All of the examples above make a single request and immediately access the
data. The full power of chinup is harnessed by instantiating a number of
Chinups at once, before accessing their response data::

    >>> chinups = [ChinupBar(token=t).get('me') for t in tokens]
    >>> len(chinups)
    40
    >>> for c in chinups: print c['first_name']
    Vincent
    Suzanne
    Aron
    Amy
    Andrew
    Cristin
    Abigail
    Daniel
    Adam
    ...

In this example, there's only a single batch request to Facebook, itself
containing 40 individual requests.  If ``settings.DEBUG`` is enabled, you
can see the count like this::

    >>> from chinup.lowlevel import batches
    >>> len(batches)
    1
    >>> len(batches[0])
    40

Django
------

If you're using chinup with Django, you can put your chinup settings in
Django's settings.py by prefixing ``CHINUP_`` like this::

    # django settings.py

    CHINUP_APP_TOKEN = 'NGAUy7KT'
    CHINUP_DEBUG = DEBUG

Additionally you can take advantage of chinup's etags caching by hooking in
the Django cache::

    CHINUP_CACHE = 'django.core.cache.cache'

django-allauth
--------------

If chinup can import `django-allauth`_, then it adds the ability to
instantiate ``ChinupBar`` with ``user`` rather than ``token``, for
example::

    >>> user = User.objects.get(username='aron')
    >>> ChinupBar(user=user).get('me')['name']
    u'Aron Griffis'

You can defer the ``User`` fetch to chinup by passing a username or primary
key::

    >>> ChinupBar(user='aron').get('me')['name']
    u'Aron Griffis'

.. _django-allauth: http://www.intenct.nl/projects/django-allauth/
