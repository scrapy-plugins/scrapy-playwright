import logging
from pathlib import Path

from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageCoroutine


class HandleTimeoutMiddleware:
    def process_exception(self, request, exception, spider):
        logging.info("Caught exception: %s", exception.__class__)
        return Request(
            url="https://httpbin.org/get",
            meta={
                "playwright": True,
                "playwright_page_coroutines": [
                    PageCoroutine(
                        "screenshot", path=Path(__file__).parent / "recovered.png", full_page=True
                    ),
                ],
            },
        )


class HandleExceptionSpider(Spider):
    """
    Handle exceptions in the Playwright downloader, such as TimeoutError
    """

    name = "awesome"
    custom_settings = {
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 1000,
        "DOWNLOADER_MIDDLEWARES": {
            HandleTimeoutMiddleware: 100,
        },
    }

    def start_requests(self):
        yield Request(
            url="https://httpbin.org/delay/300",
            meta={"playwright": True},
        )

    def parse(self, response):
        yield {"url": response.url}


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            "RETRY_TIMES": 0,
        }
    )
    process.crawl(HandleExceptionSpider)
    process.start()
