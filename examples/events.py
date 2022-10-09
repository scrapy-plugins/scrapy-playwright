from playwright.async_api import Dialog, Response as PlaywrightResponse
from scrapy import Spider, Request
from scrapy_playwright.page import PageMethod


class EventsSpider(Spider):
    """Handle page events."""

    name = "events"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    def start_requests(self):
        yield Request(
            url="https://example.org",
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    PageMethod("evaluate", "alert('foobar');"),
                ],
                "playwright_page_event_handlers": {
                    "dialog": self.handle_dialog,
                    "response": "handle_response",
                },
            },
        )

    async def handle_dialog(self, dialog: Dialog) -> None:
        self.logger.info(f"Handled dialog with message: {dialog.message}")
        await dialog.dismiss()

    async def handle_response(self, response: PlaywrightResponse) -> None:
        self.logger.info(f"Received response with URL {response.url}")

    def parse(self, response):
        return {"url": response.url}
