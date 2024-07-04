import asyncio

from scrapy import Spider, Request


class RemoteSpider(Spider):
    """Connect to a remote chromium instance."""

    name = "scroll"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        # "PLAYWRIGHT_CDP_URL": "ws://localhost:3000",
        "PLAYWRIGHT_CONNECT_URL": "ws:/localhost:61915/377758c4-4b49-41fe-9187-e4114197dea4",
    }

    def start_requests(self):
        yield Request(url="https://example.com", meta={"playwright": True})

    async def parse(self, response, **kwargs):
        await asyncio.sleep(6)
        yield {"url": response.url}
        yield Request(url="https://example.org", meta={"playwright": True})
