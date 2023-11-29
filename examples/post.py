from pathlib import Path

from scrapy import Spider, FormRequest
from scrapy_playwright.page import PageMethod


class PostSpider(Spider):
    """Send data using the POST verb."""

    name = "post"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    def start_requests(self):
        yield FormRequest(
            url="https://httpbin.org/post",
            formdata={"foo": "bar"},
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "screenshot", path=Path(__file__).parent / "post.png", full_page=True
                    ),
                ],
            },
        )

    def parse(self, response, **kwargs):
        yield {"url": response.url}
