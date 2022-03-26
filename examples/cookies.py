from pathlib import Path

from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageMethod


class CookieSpider(Spider):
    """
    Send custom cookies
    """

    name = "cookies"

    def start_requests(self):
        yield Request(
            url="https://httpbin.org/cookies",
            cookies={"foo": "bar"},
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "screenshot", path=Path(__file__).parent / "cookies.png", full_page=True
                    ),
                ],
            },
        )

    def parse(self, response):
        return {"url": response.url}


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
    process.crawl(CookieSpider)
    process.start()
