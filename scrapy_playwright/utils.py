import functools
import inspect
from typing import Callable

from ._utils import _ThreadedLoopAdapter


async def _run_async_gen(asyncgen):
    async for item in asyncgen:
        yield item


def use_threaded_loop(callback) -> Callable:
    """Wrap a coroutine callback so that Playwright coroutines are executed in
    the threaded event loop.

    On windows, Playwright runs in an event loop of its own in a separate thread.
    If Playwright coroutines are awaited directly, they are assigned to the main
    thread's event loop, resulting in: "ValueError: The future belongs to a
    different loop than the one specified as the loop argument"

    Usage:
    ```
    from playwright.async_api import Page
    from scrapy_playwright.utils import use_threaded_loop

    @use_threaded_loop
    async def parse(self, response):
        page: Page = response.meta["playwright_page"]
        await page.screenshot(path="example.png", full_page=True)
    ```
    """

    if not inspect.iscoroutinefunction(callback) and not inspect.isasyncgenfunction(callback):
        raise RuntimeError(
            f"Cannot decorate callback '{callback.__name__}' with 'use_threaded_loop':"
            " callback must be a coroutine function or an async generator"
        )

    @functools.wraps(callback)
    async def async_func_wrapper(*args, **kwargs):
        future = _ThreadedLoopAdapter._ensure_future(callback(*args, **kwargs))
        return await future

    @functools.wraps(callback)
    async def async_gen_wrapper(*args, **kwargs):
        asyncgen = _run_async_gen(callback(*args, **kwargs))
        future = _ThreadedLoopAdapter._ensure_future(asyncgen)
        for item in await future:
            yield item

    if inspect.isasyncgenfunction(callback):
        return async_gen_wrapper
    return async_func_wrapper
