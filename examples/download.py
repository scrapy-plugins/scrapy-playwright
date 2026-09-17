from pathlib import Path

from scrapy import Spider, Request


class DownloadSpider(Spider):
    name = "download"
    custom_settings = {
        "ADDONS": {"scrapy_playwright.Addon": 100},
    }

    async def start(self):
        for req in self.start_requests():
            yield req

    def start_requests(self):
        yield Request(url="https://example.org", meta={"playwright": True})
        yield Request(
            url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            meta={"playwright": True},
        )

    def parse(self, response, **kwargs):
        if filename := response.meta.get("playwright_suggested_filename"):
            (Path(__file__).parent / filename).write_bytes(response.body)
        yield {
            "url": response.url,
            "response_cls": response.__class__.__name__,
            "first_bytes": response.body[:60],
            "filename": filename,
        }
