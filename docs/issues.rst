.. _issues:

======
Issues
======

Known issues
============

-   Specifying a proxy through the ``proxy`` :attr:`Request.meta
    <scrapy.http.Request.meta>` key is not supported. See :ref:`proxies`.

-   The :signal:`headers_received <scrapy:headers_received>` and
    :signal:`bytes_received <scrapy:bytes_received>` signals are not fired.


Reporting issues
================

Before opening an issue, make sure the unexpected behavior can only be
observed by using this package, and not with standalone Playwright. To do
that, translate your spider code to a reasonably close Playwright script; if
the issue also occurs that way, report it `upstream
<https://github.com/microsoft/playwright-python>`__ instead. For instance:

.. code-block:: python

    import scrapy


    class ExampleSpider(scrapy.Spider):
        name = "example"

        async def start(self):
            yield scrapy.Request(
                url="https://example.org",
                meta=dict(
                    playwright=True,
                    playwright_page_methods=[
                        PageMethod("screenshot", path="example.png", full_page=True),
                    ],
                ),
            )

translates roughly to:

.. code-block:: python

    import asyncio

    from playwright.async_api import async_playwright


    async def main():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.goto("https://example.org")
            await page.screenshot(path="example.png", full_page=True)
            await browser.close()


    asyncio.run(main())


Software versions
-----------------

Include the versions of Scrapy, Playwright and scrapy-playwright that you are
using:

.. code-block:: shell

    playwright --version
    python -c "import scrapy_playwright; print(scrapy_playwright.__version__)"
    scrapy version -v


Reproducible code example
-------------------------

Include a `minimal, reproducible example
<https://stackoverflow.com/help/minimal-reproducible-example>`__ that shows the
reported behavior. Make the code as self-contained as possible, so that an
active Scrapy project is not required and the spider can be executed directly
from a file with :command:`runspider <scrapy:runspider>`. That usually means
including the relevant settings in the :ref:`custom_settings
<scrapy:spider-settings>` attribute of the spider:

.. code-block:: python

    import scrapy


    class ExampleSpider(scrapy.Spider):
        name = "example"
        custom_settings = {
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
        }

        async def start(self):
            yield scrapy.Request(
                url="https://example.org",
                meta={"playwright": True},
            )

Reduce the code to the minimum that still displays the issue. It is very rare
that a complete project, including middlewares, pipelines, item processing,
etc. is really needed to reproduce an issue. Reports that do not show an actual
debugging attempt will not be considered.


Logs and stats
--------------

Logs for spider jobs displaying the issue in detail are extremely useful to
understand possible bugs. Include lines before and after the problem, not just
isolated tracebacks. The job stats displayed at the end of the job are also
important.
