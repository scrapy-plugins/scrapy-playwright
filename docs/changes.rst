=============
Release notes
=============

Deprecated features are supported for at least six months following the
release that deprecated them. After that, they may be removed at any time.

0.0.48 (2026-07-10)
===================

-   Support for third-party browser providers (``PLAYWRIGHT_BROWSER_PROVIDER``
    setting)

0.0.47 (2026-06-13)
===================

-   Python 3.14 support (:gh:`375`)

-   Migrate to pyproject.toml (:gh:`374`)

-   Better response/download event handling (:gh:`372`)

-   Suppress ``PlaywrightError`` when accessing response attributes (:gh:`364`)

-   Release semaphore on context creation failure (:gh:`369`)

-   Release semaphore on page creation failure (:gh:`368`)

-   Clear contexts dict after closing them

-   Remove deprecated positional argument handling for
    ``PLAYWRIGHT_PROCESS_REQUEST_HEADERS`` (:gh:`362`)

0.0.46 (2026-01-21)
===================

-   Threaded loop updates & fixes (:gh:`361`)

0.0.45 (2026-01-16)
===================

-   Scrapy 2.14 compatibility (:gh:`356`, :gh:`359`)

0.0.44 (2025-08-13)
===================

-   Fix crawl getting stuck on Windows with Scrapy>=2.13 (:gh:`351`)

0.0.43 (2025-02-22)
===================

-   Only register request and response loggers when needed (:gh:`336`)

0.0.42 (2024-11-06)
===================

-   Allow custom PageMethod callbacks (:gh:`318`)

-   Fix download errors caused by Content-Encoding header (:gh:`322`)

0.0.41 (2024-08-13)
===================

-   Keyword arguments for PLAYWRIGHT_PROCESS_REQUEST_HEADERS, pass additional
    Request data (:gh:`303`). Deprecated positional argument handling for the
    function passed to the PLAYWRIGHT_PROCESS_REQUEST_HEADERS setting,
    arguments should now be handled by keyword.

-   Retry to create page on browser crash (:gh:`305`)

-   Fix typo in log message (:gh:`312`)

0.0.40 (2024-07-16)
===================

-   Enforce asyncio reactor in all platforms (:gh:`298`)

-   Allow multiple handlers in separate thread (:gh:`299`)

0.0.39 (2024-07-11)
===================

-   Return proper status and headers for downloads (:gh:`293`)

-   Restart on browser crash (:gh:`295`)

-   Override method and/or body only for the first matching request (:gh:`297`)

0.0.38 (2024-07-06)
===================

-   Fix freezing on responses with status 204 (:gh:`292`)

-   Connect to remote browser using BrowserType.connect (:gh:`283`)

0.0.37 (2024-07-03)
===================

-   Improve Windows concurrency (:gh:`286`)

0.0.36 (2024-06-24)
===================

-   Windows support (:gh:`276`)

0.0.35 (2024-06-01)
===================

-   Update exception message check

0.0.34 (2024-01-01)
===================

-   Update dev status classifier to 4 - beta

-   Official Python 3.12 support (:gh:`254`)

-   Custom memusage extension (:gh:`257`)

0.0.33 (2023-10-19)
===================

-   Handle downloads as binary responses (:gh:`228`)

0.0.32 (2023-09-04)
===================

-   Connect to browser using CDP (:gh:`227`)

0.0.31 (2023-08-28)
===================

-   Do not fail when getting referer header for debug log messages (:gh:`225`)

-   Do not override headers with values from asset requests (:gh:`226`)

0.0.30 (2023-08-17)
===================

-   Fix page_init_callback duplication (:gh:`222`)

-   Bump minimum Python version from 3.7 to 3.8 (:gh:`223`)

0.0.29 (2023-08-11)
===================

-   Set exc_info=True for warning log records (:gh:`219`)

-   Invoke page_init_callback after setting route (:gh:`205`)

0.0.28 (2023-08-05)
===================

-   Retry page.content if necessary (:gh:`218`)

0.0.27 (2023-07-24)
===================

-   Override method only for navigation requests (:gh:`177`)

-   Pass spider argument to _create_browser_context (:gh:`212`)

-   await AsyncPlaywright.stop on close (:gh:`214`)

0.0.26 (2023-02-01)
===================

-   Fix logging (pass extra args instead of updating log record factory)

-   Miscellaneous adjustments (naming, typing, etc)

0.0.25 (2023-01-24)
===================

-   Set spider attribute on log records

0.0.24 (2022-12-04)
===================

-   Fix request method override

0.0.23 (2022-11-27)
===================

-   Set redirect request metadata

0.0.22 (2022-10-09)
===================

-   Remove deprecated code (``PageCoroutine`` class,
    ``playwright_page_coroutines`` request meta key, ``use_playwright_headers``
    function).

-   ``playwright_page_init_callback`` meta key (page initialization callback)

0.0.21 (2022-08-08)
===================

-   Fixed TypeError exception when getting server IP address

0.0.20 (2022-08-03)
===================

-   Don't raise exceptions if ``Page.goto`` returns ``None``

0.0.19 (2022-07-17)
===================

-   Add support for ``Page.goto`` keyword arguments
    (``playwright_page_goto_kwargs`` request meta key)

0.0.18 (2022-06-18)
===================

-   Always override request headers

0.0.17 (2022-05-22)
===================

-   Support for persistent contexts

-   Limit concurrent context count (``PLAYWRIGHT_MAX_CONTEXTS`` setting)

0.0.16 (2022-05-14)
===================

-   Use new headers API introduced in Playwright 1.15 (bump required Playwright
    version)

-   Deprecate ``scrapy_playwright.headers.use_playwright_headers``, set
    ``PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None`` instead

0.0.15 (2022-05-08)
===================

-   Remove deprecated ``PLAYWRIGHT_CONTEXT_ARGS`` setting

-   Warn on failed requests

-   ``PLAYWRIGHT_ABORT_REQUEST`` setting: accept coroutine functions

-   ``PLAYWRIGHT_PROCESS_REQUEST_HEADERS`` setting: accept sync functions to
    process headers

-   Set ``playwright_page`` request meta key early

0.0.14 (2022-03-26)
===================

-   Renamed ``scrapy_playwright.page.PageCoroutine`` to
    ``scrapy_playwright.page.PageMethod`` (``PageCoroutine`` is now
    deprecated). Also deprecated the ``playwright_page_coroutines`` Request
    meta key in favor of ``playwright_page_methods``.

0.0.13 (2022-03-24)
===================

-   PageCoroutine checks

-   Fix encoding detection

-   Ability to abort requests via setting

0.0.12 (2022-03-15)
===================

-   Avoid exceptions during cleanup when the browser could not start

-   Warn when non PageCoroutine objects are passed to
    Request.meta.playwright_page_coroutines

0.0.11 (2022-03-12)
===================

-   Set the maximum amount of pages per context

-   Response.ip_address attribute

-   Response security details

0.0.10 (2022-03-02)
===================

-   Fix response encoding detection

0.0.9 (2022-01-27)
==================

-   Ability to process request headers

0.0.8 (2022-01-13)
==================

-   Fix PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT setting (allow zero value)

0.0.7 (2021-10-20)
==================

-   Log all requests/responses (debug level)

0.0.6 (2021-10-19)
==================

-   Page event handlers

-   Python 3.10 support

-   Doc fixes

-   Override User-Agent header

0.0.5 (2021-08-20)
==================

-   Improve garbage collection by removing unnecessary reference

0.0.4 (2021-07-16)
==================

-   Add support for multiple browser contexts (:gh:`13`)

-   Deprecate ``PLAYWRIGHT_CONTEXT_ARGS`` setting in favor of
    ``PLAYWRIGHT_CONTEXTS``

0.0.3 (2021-02-22)
==================

-   Snake case (requires playwright-python >= `v1.8.0a1
    <https://github.com/microsoft/playwright-python/releases/tag/v1.8.0a1>`__)

0.0.2 (2021-01-13)
==================

-   ``PLAYWRIGHT_CONTEXT_ARGS`` setting (ability to pass keyword arguments to
    the browser context)

0.0.1 (2020-12-18)
==================

Initial public release.
