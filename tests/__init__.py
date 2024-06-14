import inspect
import platform
from contextlib import asynccontextmanager

import pytest
from scrapy import Request
from scrapy.http.response.html import HtmlResponse
from scrapy.utils.test import get_crawler


if platform.system() == "Windows":
    from scrapy_playwright.handler import windows_get_result

    def windows_pytest_mark_asyncio(pytest_mark_asyncio):
        def wrapper(*args, **kwargs):
            if args and inspect.iscoroutinefunction(args[0]):

                async def method_proxy(*x):
                    await windows_get_result(args[0](*x))

                return pytest_mark_asyncio(method_proxy)
            return windows_pytest_mark_asyncio(pytest_mark_asyncio(*args, **kwargs))

        return wrapper

    pytest.mark.asyncio = windows_pytest_mark_asyncio(pytest.mark.asyncio)


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
