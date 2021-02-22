from pathlib import Path

from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageCoroutine


class ScrollSpider(Spider):
    """
    Scroll down on an infinite-scroll page
    """
    name = "scroll"

    def start_requests(self):
        yield Request(
            url="http://quotes.toscrape.com/scroll",
            cookies={"foo": "bar", "asdf": "qwerty"},
            meta={
                "playwright": True,
                "playwright_page_coroutines": [
                    PageCoroutine("wait_for_selector", "div.quote"),
                    PageCoroutine("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                    PageCoroutine("wait_for_selector", "div.quote:nth-child(11)"),  # 10 per page
                    PageCoroutine("screenshot", path=Path(__file__).parent / "scroll.png", full_page=True),
                ],
            },
        )

    def parse(self, response):
        return {"url": response.url, "count": len(response.css("div.quote"))}


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
    process.crawl(ScrollSpider)
    process.start()
