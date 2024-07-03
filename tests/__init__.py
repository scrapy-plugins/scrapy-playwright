import asyncio
import inspect
import logging
import platform
from contextlib import asynccontextmanager
from functools import wraps

from scrapy import Request
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.test import get_crawler


logger = logging.getLogger("scrapy-playwright-tests")


if platform.system() == "Windows":
    from scrapy_playwright._utils import _ThreadedLoopAdapter

    def allow_windows(test_method):
        """Wrap tests with the _ThreadedLoopAdapter class on Windows."""
        if not inspect.iscoroutinefunction(test_method):
            raise RuntimeError(f"{test_method} must be an async def method")

        @wraps(test_method)
        async def wrapped(self, *args, **kwargs):
            _ThreadedLoopAdapter.start()
            coro = test_method(self, *args, **kwargs)
            asyncio.run_coroutine_threadsafe(coro=coro, loop=_ThreadedLoopAdapter._loop).result()
            _ThreadedLoopAdapter.stop()

        return wrapped

else:

    def allow_windows(test_method):
        return test_method


@asynccontextmanager
async def make_handler(settings_dict: dict):
    """Convenience function to obtain an initialized handler and close it gracefully"""
    from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler

    settings_dict.setdefault("TELNETCONSOLE_ENABLED", False)
    crawler = get_crawler(settings_dict=settings_dict)
    handler = ScrapyPlaywrightDownloadHandler(crawler=crawler)
    try:
        await handler._launch()
    except:  # noqa (E722), pylint: disable=bare-except
        pass
    else:
        yield handler
    finally:
        await handler._close()


def assert_correct_response(response: HtmlResponse, request: Request) -> None:
    assert isinstance(response, HtmlResponse)
    assert response.request is request
    assert response.url == request.url
    assert response.status == 200
    assert "playwright" in response.flags
