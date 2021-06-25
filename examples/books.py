import hashlib
from pathlib import Path
from typing import Generator

from scrapy import Spider
from scrapy.crawler import CrawlerProcess
from scrapy.http.response import Response


class BooksSpider(Spider):
    """Extract all books, save screenshots."""

    name = "books"
    start_urls = ["http://books.toscrape.com"]
    custom_settings = {
        "CLOSESPIDER_ITEMCOUNT": 100,
        "CONCURRENT_REQUESTS": 32,
        "FEEDS": {
            "books.json": {"format": "json", "encoding": "utf-8", "indent": 4},
        },
    }

    def parse(self, response: Response) -> Generator:
        page_count = response.css(".pager .current::text").re_first(r"Page \d+ of (\d+)")
        page_count = int(page_count)
        for page in range(2, page_count + 1):
            yield response.follow(f"/catalogue/page-{page}.html")

        for book in response.css("article.product_pod a"):
            yield response.follow(
                book,
                callback=self.parse_book,
                meta={"playwright": True, "playwright_include_page": True},
            )

    async def parse_book(self, response: Response) -> dict:
        url_md5 = hashlib.md5(response.url.encode("utf-8")).hexdigest()
        page = response.meta["playwright_page"]
        await page.screenshot(
            path=Path(__file__).parent / "books" / f"{url_md5}.png", full_page=True
        )
        await page.close()
        return {
            "url": response.url,
            "title": response.css("h1::text").get(),
            "price": response.css("p.price_color::text").get(),
            "breadcrumbs": response.css(".breadcrumb a::text").getall(),
            "image": f"books/{url_md5}.png",
        }


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                # "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
        }
    )
    process.crawl(BooksSpider)
    process.start()
