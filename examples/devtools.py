from pathlib import Path

from scrapy import Spider, FormRequest
from scrapy_playwright.page import PageMethod


class RemoteBrowserSpider(Spider):
    name = "remote"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_CDP_URL": "http://127.0.0.1:9222",
        "PLAYWRIGHT_CDP_KWARGS": {"slow_mo": 2000},
        "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},  # ignored
    }

    def start_requests(self):
        yield FormRequest(
            url="https://httpbin.org/post",
            formdata={"foo": "bar"},
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod(
                        "screenshot",
                        path=Path(__file__).parent / "devtools_post.png",
                        full_page=True,
                    ),
                ],
            },
        )

    def parse(self, response):
        yield {"url": response.url}
