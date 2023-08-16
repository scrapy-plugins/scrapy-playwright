import asyncio
import platform
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from uuid import uuid4

import pytest
from playwright.async_api import Browser, TimeoutError as PlaywrightTimeoutError
from scrapy import Spider, Request
from scrapy_playwright.page import PageMethod

from tests import make_handler
from tests.mockserver import StaticMockServer


class MixinTestCaseMultipleContexts:
    @pytest.mark.asyncio
    async def test_contexts_max_settings(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1234,
        }
        async with make_handler(settings) as handler:
            assert handler.max_pages_per_context == 1234

        settings = {"PLAYWRIGHT_BROWSER_TYPE": self.browser_type, "CONCURRENT_REQUESTS": 9876}
        async with make_handler(settings) as handler:
            assert handler.max_pages_per_context == 9876

        settings = {"PLAYWRIGHT_BROWSER_TYPE": self.browser_type, "PLAYWRIGHT_MAX_CONTEXTS": None}
        async with make_handler(settings) as handler:
            assert not hasattr(handler, "context_semaphore")

        settings = {"PLAYWRIGHT_BROWSER_TYPE": self.browser_type, "PLAYWRIGHT_MAX_CONTEXTS": 1234}
        async with make_handler(settings) as handler:
            assert handler.context_semaphore._value == 1234

    @pytest.mark.asyncio
    async def test_context_kwargs(self):
        settings_dict = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {
                "default": {"java_script_enabled": False},
            },
        }
        async with make_handler(settings_dict) as handler:
            with StaticMockServer() as server:
                req = Request(
                    url=server.urljoin("/scroll.html"),
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            # cause a timeout by waiting on an element that is rendered with js
                            PageMethod("wait_for_selector", selector="div.quote", timeout=1000),
                        ],
                    },
                )
                with pytest.raises(PlaywrightTimeoutError):
                    await handler._download_request(req, Spider("foo"))

    @pytest.mark.asyncio
    async def test_contexts_max_pages(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 2,
            "PLAYWRIGHT_CONTEXTS": {
                "a": {"java_script_enabled": True},
                "b": {"java_script_enabled": True},
            },
        }
        async with make_handler(settings) as handler:
            with StaticMockServer() as server:
                requests = [
                    handler._download_request(
                        Request(
                            server.urljoin(f"/index.html?a={i}"),
                            meta={"playwright": True, "playwright_context": "a"},
                        ),
                        Spider("foo"),
                    )
                    for i in range(20)
                ] + [
                    handler._download_request(
                        Request(
                            server.urljoin(f"/index.html?b={i}"),
                            meta={"playwright": True, "playwright_context": "b"},
                        ),
                        Spider("foo"),
                    )
                    for i in range(20)
                ]
                await asyncio.gather(*requests)

            assert handler.stats.get_value("playwright/page_count/max_concurrent") == 4

    @pytest.mark.asyncio
    async def test_max_contexts(self):
        def cb_close_context(task):
            response = task.result()
            asyncio.create_task(response.meta["playwright_page"].context.close())

        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_MAX_CONTEXTS": 4,
        }
        async with make_handler(settings) as handler:
            with StaticMockServer() as server:
                tasks = []
                for i in range(20):
                    request = Request(
                        url=server.urljoin(f"/index.html?a={i}"),
                        callback=cb_close_context,
                        meta={
                            "playwright": True,
                            "playwright_include_page": True,
                            "playwright_context": f"ctx-{i}",
                        },
                    )
                    coro = handler._download_request(
                        request=request,
                        spider=Spider("foo"),
                    )
                    # callbacks are not invoked at the download handler, call them explicitly
                    task = asyncio.create_task(coro)
                    task.add_done_callback(request.callback)
                    tasks.append(task)
                await asyncio.gather(*tasks)

            assert handler.stats.get_value("playwright/context_count/max_concurrent") == 4

    @pytest.mark.asyncio
    async def test_contexts_startup(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXTS": {
                "first": {
                    "storage_state": {
                        "cookies": [
                            {
                                "url": "https://example.org",
                                "name": "foo",
                                "value": "bar",
                            },
                        ],
                    },
                },
            },
        }
        async with make_handler(settings) as handler:
            assert len(handler.context_wrappers) == 1

            with StaticMockServer() as server:
                meta = {
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_context": "first",
                }
                req = Request(server.urljoin("/index.html"), meta=meta)
                resp = await handler._download_request(req, Spider("foo"))

            page = resp.meta["playwright_page"]
            storage_state = await page.context.storage_state()
            await page.close()
            await page.context.close()
            cookie = storage_state["cookies"][0]
            assert cookie["name"] == "foo"
            assert cookie["value"] == "bar"
            assert cookie["domain"] == "example.org"

    @pytest.mark.asyncio
    async def test_persistent_context(self):
        temp_dir = f"{tempfile.gettempdir()}/{uuid4()}"
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 3000,
            "PLAYWRIGHT_CONTEXTS": {
                "persistent": {
                    "user_data_dir": temp_dir,
                },
            },
        }
        assert not Path(temp_dir).exists()
        async with make_handler(settings) as handler:
            assert Path(temp_dir).is_dir()
            assert len(handler.context_wrappers) == 1
            assert handler.context_wrappers["persistent"].persistent
            assert not hasattr(handler, "browser")

    @pytest.mark.asyncio
    async def test_mixed_persistent_contexts(self):
        temp_dir = f"{tempfile.gettempdir()}/{uuid4()}"
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 3000,
            "PLAYWRIGHT_CONTEXTS": {
                "persistent": {
                    "user_data_dir": temp_dir,
                },
                "non-persistent": {
                    "java_script_enabled": False,
                },
            },
        }
        assert not Path(temp_dir).exists()
        async with make_handler(settings) as handler:
            assert Path(temp_dir).is_dir()
            assert len(handler.context_wrappers) == 2
            assert handler.context_wrappers["persistent"].persistent
            assert not handler.context_wrappers["non-persistent"].persistent
            assert isinstance(handler.browser, Browser)

    @pytest.mark.asyncio
    async def test_contexts_dynamic(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            assert len(handler.context_wrappers) == 0

            with StaticMockServer() as server:
                meta = {
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_context": "new",
                    "playwright_context_kwargs": {
                        "storage_state": {
                            "cookies": [
                                {
                                    "url": "https://example.org",
                                    "name": "asdf",
                                    "value": "qwerty",
                                },
                            ],
                        },
                    },
                }
                req = Request(server.urljoin("/index.html"), meta=meta)
                resp = await handler._download_request(req, Spider("foo"))

            assert len(handler.context_wrappers) == 1

            page = resp.meta["playwright_page"]
            storage_state = await page.context.storage_state()
            await page.close()
            cookie = storage_state["cookies"][0]
            assert cookie["name"] == "asdf"
            assert cookie["value"] == "qwerty"
            assert cookie["domain"] == "example.org"


class TestCaseMultipleContextsChromium(IsolatedAsyncioTestCase, MixinTestCaseMultipleContexts):
    browser_type = "chromium"


class TestCaseMultipleContextsFirefox(IsolatedAsyncioTestCase, MixinTestCaseMultipleContexts):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseMultipleContextsWebkit(IsolatedAsyncioTestCase, MixinTestCaseMultipleContexts):
    browser_type = "webkit"
