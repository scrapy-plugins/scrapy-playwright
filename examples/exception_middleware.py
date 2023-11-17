import logging
from pathlib import Path

from scrapy import Spider, Request
from scrapy_playwright.page import PageMethod


class HandleTimeoutMiddleware:
    def process_exception(self, request, exception, spider):
        new_url = "https://httpbin.org/get"
        logging.info(
            "Caught exception: %s for request %s, recovering to %s",
            exception.__class__,
            request,
            new_url,
        )
        return Request(
            url=new_url,
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "screenshot", path=Path(__file__).parent / "recovered.png", full_page=True
                    ),
                ],
            },
        )


class HandleExceptionInMiddlewareSpider(Spider):
    """Handle exceptions in the Playwright downloader, such as TimeoutError"""

    name = "awesome"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 1000,  # milliseconds
        "DOWNLOADER_MIDDLEWARES": {
            HandleTimeoutMiddleware: 100,
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "RETRY_TIMES": 0,
    }

    def start_requests(self):
        yield Request(
            url="https://httpbin.org/delay/10",
            meta={"playwright": True},
        )

    def parse(self, response, **kwargs):
        logging.info("Received response for %s", response.url)
        yield {"url": response.url}
