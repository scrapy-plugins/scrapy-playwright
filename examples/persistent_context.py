from pathlib import Path

from scrapy import Spider, Request


class PersistentContextSpider(Spider):
    """Use a persistent browser context"""

    name = "persistent_context"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        ""
        "PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS": {
            "user_data_dir": str(Path.home() / "playwright-persistent-context"),
            "java_script_enabled": False,
            "extra_http_headers": {"Asdf": "Qwerty"},
            "user_agent": "foobar",
        },
        "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,
    }

    def start_requests(self):
        yield Request(url="https://httpbin.org/get", meta={"playwright": True})

    def parse(self, response):
        content = response.css("pre::text").get()
        print(content)
        return {
            "url": response.url,
            "context": response.meta["playwright_context"],
        }
