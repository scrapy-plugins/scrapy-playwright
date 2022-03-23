from contextlib import asynccontextmanager, suppress

from scrapy.utils.test import get_crawler


@asynccontextmanager
async def make_handler(settings_dict: dict):
    """Convenience function to obtain an initialized handler and close it gracefully"""
    from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler

    crawler = get_crawler(settings_dict=settings_dict)
    handler = ScrapyPlaywrightDownloadHandler(crawler=crawler)
    with suppress(Exception):
        await handler._launch_browser()
        yield handler
    await handler._close()
