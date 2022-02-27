import logging
import re
from pathlib import Path

from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy.http.response import Response


class BooksSpider(Spider):
    """Extract all books, save screenshots."""

    name = "books_abort_route"

    def start_requests(self) -> list:
        return [
            Request(
                "http://books.toscrape.com",
                meta={"playwright": True, "playwright_include_page": True},
            )
        ]

    async def parse(self, response: Response) -> None:
        page = response.meta["playwright_page"]
        await page.screenshot(path=Path(__file__).parent / "books_abort_route.png", full_page=True)
        await page.close()


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                # "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            # "PLAYWRIGHT_ABORT_ROUTE": r"**/*.{jpg,js}",  # does not work for multiple extensions
            "PLAYWRIGHT_ABORT_ROUTE": re.compile(r"(\.jpg$)|(\.js$)"),
        }
    )
    process.crawl(BooksSpider)
    logging.getLogger("scrapy.core.engine").setLevel(logging.WARNING)
    logging.getLogger("scrapy.core.scraper").setLevel(logging.WARNING)
    process.start()
