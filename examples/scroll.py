from pathlib import Path

from scrapy import Spider, Request
from scrapy_playwright.page import PageMethod


class ScrollSpider(Spider):
    """Scroll down on an infinite-scroll page."""

    name = "scroll"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            # "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "LOG_LEVEL": "INFO",
    }

    def start_requests(self):
        yield Request(
            url="http://quotes.toscrape.com/scroll",
            cookies={"foo": "bar", "asdf": "qwerty"},
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "div.quote"),
                    PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_selector", "div.quote:nth-child(11)"),  # 10 per page
                    PageMethod(
                        "screenshot", path=Path(__file__).parent / "scroll.png", full_page=True
                    ),
                ],
            },
        )

    def parse(self, response, **kwargs):
        return {"url": response.url, "count": len(response.css("div.quote"))}
