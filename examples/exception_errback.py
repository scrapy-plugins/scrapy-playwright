import logging

from scrapy import Spider, Request


class HandleExceptionInErrbackSpider(Spider):
    """Handle exceptions in the Playwright downloader, such as TimeoutError"""

    name = "awesome"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 1000,  # milliseconds
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
            errback=self.errback,
        )

    def errback(self, failure):
        logging.info(
            "Handling failure in errback, request=%r, exception=%r", failure.request, failure.value
        )
