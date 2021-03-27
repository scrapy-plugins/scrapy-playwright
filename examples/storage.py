from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
from scrapy_playwright.page import PageCoroutine


class StorageSpider(Spider):
    """
    Set and get storage state
    """
    name = "storage"

    def start_requests(self):
        yield Request(
            url="https://example.org",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_coroutines": [
                    PageCoroutine("evaluate_handle", "window.localStorage.setItem('foo', 'bar');"),
                ],
            },
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        return {"url": response.url, "storage_state": await page.context.storage_state()}


if __name__ == "__main__":
    process = CrawlerProcess(
        settings={
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "DOWNLOAD_HANDLERS": {
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                # "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
        }
    )
    process.crawl(StorageSpider)
    process.start()
