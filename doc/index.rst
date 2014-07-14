chinup
======

.. This is commented until we're running on Travis.
   |Build Status|

**Chinup** is a high-performance Python client for interacting with the
Facebook Graph API. It features automatic request batching, transparent
etags support, and support for paged responses.

If you're new to chinup, take a look at the :doc:`quickstart <quickstart>`.
The full API is detailed in the :doc:`API reference <api>`.

Installation
------------

Install using ``pip`` from `pypi <http://pypi.python.org/pypi/chinup>`__.
Chinup supports Python 2.7. Chinup depends on `requests
<http://pypi.python.org/pypi/requests>`__ and `URLObject
<http://pypi.python.org/pypi/URLObject>`__ which will both be installed
automatically.

.. code:: bash

    pip install chinup

Contents
--------

.. toctree::
   :maxdepth: 2

   quickstart
   advanced
   settings
   api

License
=======

Copyright 2014, SMBApps LLC.

Released under the MIT license, which reads as follows:

    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |Build Status| image:: https://secure.travis-ci.org/pagepart/chinup.png?branch=master
   :target: http://travis-ci.org/pagepart/chinup
