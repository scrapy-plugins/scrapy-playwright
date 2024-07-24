import asyncio
import functools
import inspect
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


def use_threaded_loop(callback):
    if not (inspect.iscoroutinefunction(callback) or inspect.isasyncgenfunction(callback)):
        raise RuntimeError(
            f"Cannot decorate callback '{callback.__name__}' with 'use_threaded_loop':"
            " callback must be a coroutine function or an async generator"
        )

    @functools.wraps(callback)
    async def wrapper(*args, **kwargs):
        future: asyncio.Future = _ThreadedLoopAdapter._ensure_future(callback(*args, **kwargs))
        return await future

    return wrapper
