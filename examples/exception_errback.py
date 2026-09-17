import logging

from scrapy import Spider, Request


class HandleExceptionInErrbackSpider(Spider):
    """Handle exceptions in the Playwright downloader, such as TimeoutError"""

    name = "awesome"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 1000,  # milliseconds
        "ADDONS": {"scrapy_playwright.Addon": 100},
        "RETRY_TIMES": 0,
    }

    async def start(self):
        for req in self.start_requests():
            yield req

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
