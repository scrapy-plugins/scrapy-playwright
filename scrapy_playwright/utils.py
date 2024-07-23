import asyncio

from typing import Awaitable

from ._utils import _ThreadedLoopAdapter


def ensure_future(coro: Awaitable) -> asyncio.Future:
    """Wrap a coroutine in a Future assigned to the threaded event loop.

    On windows, Playwright runs in an event loop of its own in a separate thread.
    If Playwright coroutines are awaited directly, they are assigned to the main
    thread's event loop, resulting in: "ValueError: The future belongs to a
    different loop than the one specified as the loop argument"

    Usage:
    ```
    from playwright.async_api import Page
    from scrapy_playwright import ensure_future

    async def parse(self, response):
        page: Page = response.meta["playwright_page"]
        await ensure_future(page.screenshot(path="example.png", full_page=True))
    ```
    """
    return _ThreadedLoopAdapter._ensure_future(coro)
