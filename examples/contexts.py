from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess


class MultipleContextsSpider(Spider):
    """Handle multiple browser contexts"""

    name = "contexts"
    custom_settings = {
        "PLAYWRIGHT_CONTEXTS": {
            "first": {
                "storage_state": {
                    "cookies": [
                        {
                            "url": "https://httpbin.org/headers",
                            "name": "context",
                            "value": "first",
                        },
                    ],
                },
            },
            "second": {
                "storage_state": {
                    "cookies": [
                        {
                            "url": "https://httpbin.org/headers",
                            "name": "context",
                            "value": "second",
                        },
                    ],
                },
            },
        },
    }

    def start_requests(self):
        # using existing contexts
        yield Request(
            url="https://httpbin.org/headers",
            meta={
                "playwright": True,
                "playwright_context_name": "first",
                "playwright_include_page": True,
            },
            dont_filter=True,
        )
        yield Request(
            url="https://httpbin.org/headers",
            meta={
                "playwright": True,
                "playwright_context_name": "second",
                "playwright_include_page": True,
            },
            dont_filter=True,
        )
        # create a new context
        yield Request(
            url="https://httpbin.org/headers",
            meta={
                "playwright": True,
                "playwright_context_name": "third",
                "playwright_context_kwargs": {
                    "storage_state": {
                        "cookies": [
                            {
                                "url": "https://httpbin.org/headers",
                                "name": "context",
                                "value": "third",
                            },
                        ],
                    },
                },
                "playwright_include_page": True,
            },
            dont_filter=True,
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        return {"url": response.url, "storage_state": await page.context.storage_state()}


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
        }
    )
    process.crawl(MultipleContextsSpider)
    process.start()
