=====
Pages
=====

.. _page-objects:

Receiving Page objects in callbacks
===================================

Setting the :reqmeta:`playwright_include_page` meta key to a value that
evaluates to ``True`` makes the `Page
<https://playwright.dev/python/docs/api/class-page>`__ object that downloaded
the request available in the callback, in the ``playwright_page`` meta key. To
be able to ``await`` coroutines on it, define the callback as a coroutine
function (``async def``).

.. caution:: Pages that are not closed once they are no longer needed count
    towards the :setting:`PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` limit, and the
    crawl freezes once the limit is reached. Define a request errback as well,
    so that pages are closed even if a request fails.

.. code-block:: python

    import scrapy
    from playwright.async_api import Page


    class AwesomeSpiderWithPage(scrapy.Spider):
        name = "page_spider"

        async def start(self):
            yield scrapy.Request(
                url="https://example.org",
                callback=self.parse_first,
                meta={"playwright": True, "playwright_include_page": True},
                errback=self.errback_close_page,
            )

        def parse_first(self, response):
            page: Page = response.meta["playwright_page"]
            return scrapy.Request(
                url="https://example.com",
                callback=self.parse_second,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page": page,
                },
                errback=self.errback_close_page,
            )

        async def parse_second(self, response):
            page: Page = response.meta["playwright_page"]
            title = await page.title()  # "Example Domain"
            await page.close()
            return {"title": title}

        async def errback_close_page(self, failure):
            page: Page = failure.request.meta["playwright_page"]
            await page.close()

Passing the page over from one callback to another, as ``parse_first`` does
above, works in regular callbacks; ``async def`` is only needed to ``await``
things.

Network operations resulting from awaiting a coroutine on a page (``goto``,
``go_back``, etc.) are executed directly by Playwright, bypassing the Scrapy
request workflow (scheduler, middlewares, etc.).


.. _page-methods:

Executing actions on pages
==========================

Pass a sorted iterable (e.g. :class:`list`, :class:`tuple`, :class:`dict`) of
:class:`~scrapy_playwright.page.PageMethod` objects in the
:reqmeta:`playwright_page_methods` meta key to have methods invoked on the
`Page <https://playwright.dev/python/docs/api/class-page>`__ object before
returning the final response to the callback. This is useful to perform
actions on a page, like scrolling down or clicking links, and handle only the
final result in the callback.

.. code-block:: python

    async def start(self):
        yield Request(
            url="https://example.org",
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("screenshot", path="example.png", full_page=True),
                ],
            },
        )


    def parse(self, response, **kwargs):
        screenshot = response.meta["playwright_page_methods"][0]
        # screenshot.result contains the image's bytes

That produces the same effect as:

.. code-block:: python

    async def start(self):
        yield Request(
            url="https://example.org",
            meta={"playwright": True, "playwright_include_page": True},
        )


    async def parse(self, response, **kwargs):
        page = response.meta["playwright_page"]
        screenshot = await page.screenshot(path="example.png", full_page=True)
        # screenshot contains the image's bytes
        await page.close()

Refer to the `upstream docs for the Page class
<https://playwright.dev/python/docs/api/class-page>`__ for the available
methods.


Passing callable objects
------------------------

If a :class:`~scrapy_playwright.page.PageMethod` receives a callable object as
its first argument, it is called with the page as its first argument. Any
additional arguments are passed to the callable after the page.

.. code-block:: python

    async def scroll_page(page: Page) -> str:
        await page.wait_for_selector(selector="div.quote")
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await page.wait_for_selector(selector="div.quote:nth-child(11)")
        return page.url


    class MySpider(scrapy.Spider):
        name = "scroll"

        async def start(self):
            yield Request(
                url="https://quotes.toscrape.com/scroll",
                meta={
                    "playwright": True,
                    "playwright_page_methods": [PageMethod(scroll_page)],
                },
            )


Impact on Response objects
--------------------------

Certain response attributes (e.g. ``url``, ``ip_address``, ``status``,
``headers``) reflect the state after the last action performed on a page. If a
:class:`~scrapy_playwright.page.PageMethod` results in a navigation, e.g. a
click on a link, those attributes point to the new page, which might be
different from the request URL.


.. _page-events:

Handling page events
====================

Pass a dictionary of page event handlers in the
:reqmeta:`playwright_page_event_handlers` meta key. Keys are the name of the
event to be handled (e.g. ``dialog``, ``download``). Values can be either
callables or strings, in which case a spider method with that name is looked
up.

.. code-block:: python

    from playwright.async_api import Dialog
    from playwright.async_api import Response as PlaywrightResponse


    async def handle_dialog(dialog: Dialog) -> None:
        logging.info(f"Handled dialog with message: {dialog.message}")
        await dialog.dismiss()


    class EventSpider(scrapy.Spider):
        name = "event"

        async def start(self):
            yield scrapy.Request(
                url="https://example.org",
                meta={
                    "playwright": True,
                    "playwright_page_event_handlers": {
                        "dialog": handle_dialog,
                        "response": "handle_response",
                    },
                },
            )

        async def handle_response(self, response: PlaywrightResponse) -> None:
            logging.info(f"Received response with URL {response.url}")

See the `upstream Page docs
<https://playwright.dev/python/docs/api/class-page>`__ for the accepted events
and the arguments passed to their handlers.

Event handlers remain attached to the page, and are called for subsequent
downloads using the same page unless they are `removed later
<https://playwright.dev/python/docs/events#addingremoving-event-listener>`__.
This is usually not a problem, since by default requests are performed in
single-use pages.

Event handlers process Playwright objects, not Scrapy ones. For each Scrapy
request or response there is a matching Playwright one, but not the other way
around: background requests and responses to get images, scripts, stylesheets,
etc. are not seen by Scrapy.
