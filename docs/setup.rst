.. _setup:

=============
Initial setup
=============

Requirements
============

-   Python 3.10+

-   Scrapy 2.7+

-   Playwright 1.40+

Scrapy can integrate :mod:`asyncio`-based libraries such as Playwright since
`Scrapy 2.0 <https://docs.scrapy.org/en/latest/news.html#scrapy-2-0-0-2020-03-03>`__,
which introduced :ref:`coroutine syntax support <scrapy:topics-coroutines>`
and :ref:`asyncio support <scrapy:using-asyncio>`.


Installation
============

.. code-block:: shell

    pip install scrapy-playwright

Playwright is installed as a dependency, but the browsers it drives are not,
so install the ones you plan to use:

.. code-block:: shell

    playwright install firefox chromium


.. _activation:

Activation
==========

Replace the default ``https`` and/or ``http`` download handlers through the
:setting:`DOWNLOAD_HANDLERS <scrapy:DOWNLOAD_HANDLERS>` setting, and use the
:mod:`asyncio` Twisted reactor:

.. code-block:: python

    # settings.py
    DOWNLOAD_HANDLERS = {
        "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    }
    TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

Registering the handler for ``https`` is usually enough, since most modern
sites use HTTPS. Enable the ``http`` handler only if you need to process plain
HTTP URLs with Playwright.

``ScrapyPlaywrightDownloadHandler`` inherits from the default
``http``/``https`` handler, and only handles requests that :ref:`ask for
Playwright <usage>`. The rest are processed by the regular Scrapy download
handler.

The :setting:`TWISTED_REACTOR <scrapy:TWISTED_REACTOR>` value above is the
default for projects created with Scrapy 2.7+.


Windows support
===============

On Windows, Playwright runs in a :class:`~asyncio.ProactorEventLoop` in a
separate thread. This is necessary because Playwright cannot run in the same
:mod:`asyncio` event loop as the Scrapy crawler: Playwright `runs the driver in
a subprocess
<https://github.com/microsoft/playwright-python/blob/v1.44.0/playwright/_impl/_transport.py#L120-L130>`__,
which on Windows :ref:`requires <asyncio-windows-subprocess>`
:class:`~asyncio.ProactorEventLoop`, whereas the :mod:`asyncio` Twisted reactor
`requires
<https://github.com/twisted/twisted/blob/twisted-24.3.0/src/twisted/internet/asyncioreactor.py#L31>`__
:class:`~asyncio.SelectorEventLoop`.
