from contextlib import asynccontextmanager

from scrapy.utils.test import get_crawler


@asynccontextmanager
async def make_handler(settings_dict: dict):
    """Convenience function to obtain an initialized handler and close it gracefully"""
    from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler

    try:
        crawler = get_crawler(settings_dict=settings_dict)
        handler = ScrapyPlaywrightDownloadHandler(crawler=crawler)
        await handler._launch_browser()
        yield handler
    finally:
        await handler._close()
