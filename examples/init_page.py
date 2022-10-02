import json

import scrapy


async def init_page(page):
    await page.set_extra_http_headers({"Asdf": "Qwerty"})


class InitPageSpider(scrapy.Spider):
    """A spider that initializes pages upon creation."""

    name = "init_page"
    custom_settings = {
        "PLAYWRIGHT_PROCESS_REQUEST_HEADERS": None,  # needed to keep playwright headers
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://httpbin.org/headers",
            meta={
                "playwright": True,
                "playwright_init_page": init_page,
            },
        )

    def parse(self, response):
        json_str = response.css("pre::text").get()
        print(json_str)
        data = json.loads(json_str)
        assert data["headers"]["Asdf"] == "Qwerty"
        return {"data": data}
