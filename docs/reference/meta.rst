.. _meta:

=================
Request.meta keys
=================

Keys that can be defined in :attr:`Request.meta <scrapy.http.Request.meta>`
for scrapy-playwright.

.. reqmeta:: playwright

playwright
==========

Type: :class:`bool`

Default: ``False``

If set to a value that evaluates to ``True``, the request is processed by
Playwright.

.. code-block:: python

    return scrapy.Request("https://example.org", meta={"playwright": True})


.. reqmeta:: playwright_context

playwright_context
==================

Type: :class:`str`

Default: ``"default"``

Name of the context to be used to download the request.

.. code-block:: python

    return scrapy.Request(
        url="https://example.org",
        meta={
            "playwright": True,
            "playwright_context": "awesome_context",
        },
    )

See :ref:`contexts`.


.. reqmeta:: playwright_context_kwargs

playwright_context_kwargs
=========================

Type: :class:`dict`

Default: ``{}``

Keyword arguments to be used when creating a new context, if a context with
the name specified in :reqmeta:`playwright_context` does not exist already.

.. code-block:: python

    return scrapy.Request(
        url="https://example.org",
        meta={
            "playwright": True,
            "playwright_context": "awesome_context",
            "playwright_context_kwargs": {
                "ignore_https_errors": True,
            },
        },
    )

See :ref:`create-contexts`.


.. reqmeta:: playwright_include_page

playwright_include_page
=======================

Type: :class:`bool`

Default: ``False``

If ``True``, the `Page
<https://playwright.dev/python/docs/api/class-page>`__ object used to download
the request is available in the callback, at
``response.meta["playwright_page"]``. Otherwise, the page is closed
immediately after processing the request.

.. code-block:: python

    return scrapy.Request(
        url="https://example.org",
        meta={"playwright": True, "playwright_include_page": True},
    )

Use it only if you need access to the page object in the callback; it is not
needed for the page to load or for :reqmeta:`page methods
<playwright_page_methods>` to be applied. See :ref:`page-objects`.


.. reqmeta:: playwright_page

playwright_page
===============

Type: ``playwright.async_api.Page``

Default: ``None``

A `Page <https://playwright.dev/python/docs/api/class-page>`__ object to be
used to download the request. If unspecified, a new page is created for each
request. Combined with :reqmeta:`playwright_include_page`, it allows chaining
requests on the same page:

.. code-block:: python

    from playwright.async_api import Page


    async def start(self):
        yield scrapy.Request(
            url="https://httpbin.org/get",
            meta={"playwright": True, "playwright_include_page": True},
        )


    def parse(self, response, **kwargs):
        page: Page = response.meta["playwright_page"]
        yield scrapy.Request(
            url="https://httpbin.org/headers",
            callback=self.parse_headers,
            meta={"playwright": True, "playwright_page": page},
        )


.. reqmeta:: playwright_page_event_handlers

playwright_page_event_handlers
==============================

Type: :class:`dict`

Default: ``{}``

Handlers to be attached to page events. See :ref:`page-events`.


.. reqmeta:: playwright_page_goto_kwargs

playwright_page_goto_kwargs
===========================

Type: :class:`dict`

Default: ``{}``

Keyword arguments to be passed to the `goto method
<https://playwright.dev/python/docs/api/class-page#page-goto>`__ of the page
when navigating to a URL. The ``url`` key is ignored, the request URL is used
instead.

.. code-block:: python

    return scrapy.Request(
        url="https://example.org",
        meta={
            "playwright": True,
            "playwright_page_goto_kwargs": {
                "wait_until": "networkidle",
            },
        },
    )


.. reqmeta:: playwright_page_init_callback

playwright_page_init_callback
=============================

Type: :class:`~collections.abc.Callable` or :class:`str`

Default: ``None``

A coroutine function (``async def``), or the import path of one, to be invoked
for newly created pages. It is called after attaching page event handlers and
setting up internal route handling, before making any request, and it receives
the Playwright page and the Scrapy request as positional arguments. It is
ignored if the page for the request already exists, e.g. when passing
:reqmeta:`playwright_page`.

.. code-block:: python

    async def init_page(page, request):
        await page.add_init_script(path="./custom_script.js")


    class AwesomeSpider(scrapy.Spider):
        async def start(self):
            yield scrapy.Request(
                url="https://httpbin.org/headers",
                meta={
                    "playwright": True,
                    "playwright_page_init_callback": init_page,
                },
            )

.. important:: scrapy-playwright uses ``Page.route`` and ``Page.unroute``
    internally, avoid using those methods unless you know exactly what you are
    doing.


.. reqmeta:: playwright_page_methods

playwright_page_methods
=======================

Type: :class:`~collections.abc.Iterable` of
:class:`~scrapy_playwright.page.PageMethod`

Default: ``()``

Actions to be performed on the page before returning the final response. See
:ref:`page-methods`.


.. reqmeta:: playwright_security_details

playwright_security_details
===========================

Type: :class:`dict`, read only

`Security information
<https://playwright.dev/python/docs/api/class-response#response-security-details>`__
about the response. Only available for HTTPS requests.

.. code-block:: python

    def parse(self, response, **kwargs):
        print(response.meta["playwright_security_details"])
        # {'issuer': 'DigiCert TLS RSA SHA256 2020 CA1', 'protocol': 'TLS 1.3', ...}


.. reqmeta:: playwright_suggested_filename

playwright_suggested_filename
=============================

Type: :class:`str`, read only

The value of the `Download.suggested_filename
<https://playwright.dev/python/docs/api/class-download#download-suggested-filename>`__
attribute when the response is the binary contents of a `download
<https://playwright.dev/python/docs/downloads>`__, e.g. a PDF file. Only
available for responses that only caused a download.

.. code-block:: python

    def parse(self, response, **kwargs):
        print(response.meta["playwright_suggested_filename"])
        # 'sample_file.pdf'
