.. _examples:

========
Examples
========

Click on a link, save the resulting page as PDF:

.. code-block:: python

    class ClickAndSavePdfSpider(scrapy.Spider):
        name = "pdf"

        async def start(self):
            yield scrapy.Request(
                url="https://example.org",
                meta=dict(
                    playwright=True,
                    playwright_page_methods={
                        "click": PageMethod("click", selector="a"),
                        "pdf": PageMethod("pdf", path="/tmp/file.pdf"),
                    },
                ),
            )

        def parse(self, response, **kwargs):
            pdf_bytes = response.meta["playwright_page_methods"]["pdf"].result
            with open("iana.pdf", "wb") as fp:
                fp.write(pdf_bytes)
            # response.url is "https://www.iana.org/domains/reserved"
            yield {"url": response.url}

Scroll down on an infinite scroll page, take a screenshot of the full page:

.. code-block:: python

    class ScrollSpider(scrapy.Spider):
        name = "scroll"

        async def start(self):
            yield scrapy.Request(
                url="http://quotes.toscrape.com/scroll",
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", "div.quote"),
                        PageMethod(
                            "evaluate", "window.scrollBy(0, document.body.scrollHeight)"
                        ),
                        # 10 quotes per page
                        PageMethod("wait_for_selector", "div.quote:nth-child(11)"),
                    ],
                ),
            )

        async def parse(self, response, **kwargs):
            page = response.meta["playwright_page"]
            await page.screenshot(path="quotes.png", full_page=True)
            await page.close()
            # quotes from several pages
            return {"quote_count": len(response.css("div.quote"))}

See the `examples directory
<https://github.com/scrapy-plugins/scrapy-playwright/tree/main/examples>`__ for
more.
