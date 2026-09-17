.. _settings:

========
Settings
========

:ref:`Settings <scrapy:topics-settings>` for scrapy-playwright.

.. setting:: PLAYWRIGHT_ABORT_REQUEST

PLAYWRIGHT_ABORT_REQUEST
========================

Type: :class:`~collections.abc.Callable` or :class:`str`

Default: ``None``

A predicate function, or the import path of one, that receives a `Request
<https://playwright.dev/python/docs/api/class-request>`__ object and returns
``True`` if the request should be aborted. Coroutine functions (``async def``)
are supported.

.. code-block:: python

    def should_abort_request(request):
        return request.resource_type == "image" or ".jpg" in request.url


    PLAYWRIGHT_ABORT_REQUEST = should_abort_request

All requests appear in the ``DEBUG`` level logs, but aborted requests have no
corresponding response log line. They are counted in the
``playwright/request_count/aborted`` stat.


.. setting:: PLAYWRIGHT_BROWSER_PROVIDER

PLAYWRIGHT_BROWSER_PROVIDER
===========================

Type: :class:`type` or :class:`str`

Default: :class:`scrapy_playwright.provider.PlaywrightBrowserProvider`

A class, or the import path of one, that owns the browser lifecycle: startup,
launching or connecting browsers, optional persistent contexts, and teardown.
It is instantiated with the handler configuration object as its only argument.

.. code-block:: python

    PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.CustomBrowserProvider"

The default provider wraps vanilla Playwright, and supports everything else
documented here. See :ref:`providers`.


.. setting:: PLAYWRIGHT_BROWSER_TYPE

PLAYWRIGHT_BROWSER_TYPE
=======================

Type: :class:`str`

Default: ``"chromium"``

The browser type to be launched, e.g. ``chromium``, ``firefox``, ``webkit``.

.. code-block:: python

    PLAYWRIGHT_BROWSER_TYPE = "firefox"


.. setting:: PLAYWRIGHT_CDP_KWARGS

PLAYWRIGHT_CDP_KWARGS
=====================

Type: :class:`dict`

Default: ``{}``

Additional keyword arguments for `BrowserType.connect_over_cdp
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp>`__
when using :setting:`PLAYWRIGHT_CDP_URL`. The ``endpoint_url`` key is ignored,
:setting:`PLAYWRIGHT_CDP_URL` is used instead.

.. code-block:: python

    PLAYWRIGHT_CDP_KWARGS = {
        "slow_mo": 1000,
        "timeout": 10 * 1000,
    }


.. setting:: PLAYWRIGHT_CDP_URL

PLAYWRIGHT_CDP_URL
==================

Type: :class:`str`

Default: ``None``

The endpoint of a remote Chromium browser to connect to using the `Chrome
DevTools Protocol <https://chromedevtools.github.io/devtools-protocol/>`__, via
`BrowserType.connect_over_cdp
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp>`__.

.. code-block:: python

    PLAYWRIGHT_CDP_URL = "http://localhost:9222"

When this setting is used, all non-persistent contexts are created on the
connected remote browser, :setting:`PLAYWRIGHT_LAUNCH_OPTIONS` is ignored, and
:setting:`PLAYWRIGHT_BROWSER_TYPE` must be ``"chromium"``.

It cannot be used at the same time as :setting:`PLAYWRIGHT_CONNECT_URL`.


.. setting:: PLAYWRIGHT_CONNECT_KWARGS

PLAYWRIGHT_CONNECT_KWARGS
=========================

Type: :class:`dict`

Default: ``{}``

Additional keyword arguments for `BrowserType.connect
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect>`__
when using :setting:`PLAYWRIGHT_CONNECT_URL`. The ``ws_endpoint`` key is
ignored, :setting:`PLAYWRIGHT_CONNECT_URL` is used instead.

.. code-block:: python

    PLAYWRIGHT_CONNECT_KWARGS = {
        "slow_mo": 1000,
        "timeout": 10 * 1000,
    }


.. setting:: PLAYWRIGHT_CONNECT_URL

PLAYWRIGHT_CONNECT_URL
======================

Type: :class:`str`

Default: ``None``

URL of a remote Playwright browser instance to connect to using
`BrowserType.connect
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect>`__.

.. code-block:: python

    PLAYWRIGHT_CONNECT_URL = "ws://localhost:35477/ae1fa0bc325adcfd9600d9f712e9c733"

When this setting is used, all non-persistent contexts are created on the
connected remote browser, and :setting:`PLAYWRIGHT_LAUNCH_OPTIONS` is ignored.

It cannot be used at the same time as :setting:`PLAYWRIGHT_CDP_URL`.

From the upstream Playwright docs: when connecting to another browser launched
via `BrowserType.launchServer
<https://playwright.dev/docs/api/class-browsertype#browser-type-launch-server>`__
in Node.js, the major and minor version needs to match the client version
(1.2.3 is compatible with 1.2.x).


.. setting:: PLAYWRIGHT_CONTEXTS

PLAYWRIGHT_CONTEXTS
===================

Type: :class:`dict`

Default: ``{}``

Browser contexts to be created on startup, as a mapping of context name to
keyword arguments for `Browser.new_context
<https://playwright.dev/python/docs/api/class-browser#browser-new-context>`__.

.. code-block:: python

    PLAYWRIGHT_CONTEXTS = {
        "foobar": {
            "context_arg1": "value",
            "context_arg2": "value",
        },
        "default": {
            "context_arg1": "value",
            "context_arg2": "value",
        },
        "persistent": {
            "user_data_dir": "/path/to/dir",  # will be a persistent context
            "context_arg1": "value",
        },
    }

See :ref:`contexts`.


.. setting:: PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT
=====================================

Type: :class:`float`

Default: ``None``

Timeout to be used when requesting pages by Playwright, in milliseconds. If
``None``, the Playwright default is used, 30000 ms at the time of writing. See
`BrowserContext.set_default_navigation_timeout
<https://playwright.dev/python/docs/api/class-browsercontext#browser-context-set-default-navigation-timeout>`__.

.. code-block:: python

    PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 10 * 1000  # 10 seconds


.. setting:: PLAYWRIGHT_DOWNLOAD_TIMEOUT

PLAYWRIGHT_DOWNLOAD_TIMEOUT
===========================

Type: :class:`int`

Default: ``30000`` (30 seconds)

Timeout in milliseconds to wait for a file download to start and to finish. If
the timeout is exceeded, the original navigation error is re-raised instead of
hanging indefinitely.

.. code-block:: python

    PLAYWRIGHT_DOWNLOAD_TIMEOUT = 60000  # 1 minute


.. setting:: PLAYWRIGHT_LAUNCH_OPTIONS

PLAYWRIGHT_LAUNCH_OPTIONS
=========================

Type: :class:`dict`

Default: ``{}``

Keyword arguments for `BrowserType.launch
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch>`__,
used when launching the browser.

.. code-block:: python

    PLAYWRIGHT_LAUNCH_OPTIONS = {
        "headless": False,
        "timeout": 20 * 1000,  # 20 seconds
    }


.. setting:: PLAYWRIGHT_MAX_CONTEXTS

PLAYWRIGHT_MAX_CONTEXTS
=======================

Type: :class:`int`

Default: ``None``

Maximum amount of concurrent Playwright contexts. ``None`` enforces no limit.

.. code-block:: python

    PLAYWRIGHT_MAX_CONTEXTS = 8

See :ref:`max-contexts`.


.. setting:: PLAYWRIGHT_MAX_PAGES_PER_CONTEXT

PLAYWRIGHT_MAX_PAGES_PER_CONTEXT
================================

Type: :class:`int`

Default: the value of the :setting:`CONCURRENT_REQUESTS
<scrapy:CONCURRENT_REQUESTS>` setting

Maximum amount of concurrent Playwright pages for each context.

.. code-block:: python

    PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 4

See :ref:`page-objects` for the risks of leaving pages unclosed.


.. setting:: PLAYWRIGHT_PROCESS_REQUEST_HEADERS

PLAYWRIGHT_PROCESS_REQUEST_HEADERS
==================================

Type: :class:`~collections.abc.Callable` or :class:`str`

Default: :func:`scrapy_playwright.headers.use_scrapy_headers`

A function, or the import path of one, that processes a Playwright request and
returns a ``dict[str, str]`` with headers to override. Depending on the
browser, additional default headers could be sent as well. Coroutine functions
(``async def``) are supported.

It is called at least once for every Scrapy request, and additional times if
Playwright generates more requests, e.g. to retrieve assets like images or
scripts.

It receives the following keyword arguments:

-   ``browser_type_name``: :class:`str`

-   ``playwright_request``: ``playwright.async_api.Request``

-   ``scrapy_request_data``: :class:`dict` with the ``method``
    (:class:`str`), ``url`` (:class:`str`), ``headers``
    (:class:`scrapy.http.headers.Headers`), ``body`` (:class:`bytes` or
    ``None``) and ``encoding`` (:class:`str`) of the Scrapy request

.. code-block:: python

    async def custom_headers(
        *,
        browser_type_name: str,
        playwright_request: playwright.async_api.Request,
        scrapy_request_data: dict,
    ) -> dict[str, str]:
        headers = await playwright_request.all_headers()
        scrapy_headers = scrapy_request_data["headers"].to_unicode_dict()
        headers["Cookie"] = scrapy_headers.get("Cookie")
        return headers


    PLAYWRIGHT_PROCESS_REQUEST_HEADERS = custom_headers

The default function emulates the Scrapy behavior for navigation requests,
i.e. it overrides headers with their values from the Scrapy request. For
non-navigation requests, e.g. images, stylesheets or scripts, it only
overrides the ``User-Agent`` header, for consistency.

Setting this to ``None`` gives complete control to Playwright: headers from
Scrapy requests are ignored, and only headers set by Playwright are sent. That
includes headers passed through the :attr:`Request.headers
<scrapy.http.Request.headers>` attribute or set by Scrapy components, and
cookies set through the :attr:`Request.cookies
<scrapy.http.Request.cookies>` attribute.


.. setting:: PLAYWRIGHT_RESTART_DISCONNECTED_BROWSER

PLAYWRIGHT_RESTART_DISCONNECTED_BROWSER
=======================================

Type: :class:`bool`

Default: ``True``

Whether the browser is restarted if it gets disconnected, for instance if the
local browser crashes or a remote connection times out.

It is implemented by listening to the `disconnected browser event
<https://playwright.dev/python/docs/api/class-browser#browser-event-disconnected>`__,
so it does not apply to :ref:`persistent contexts <persistent-contexts>`,
since `BrowserType.launch_persistent_context
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context>`__
returns the context directly.
