import asyncio
import logging
import platform
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from scrapy import Spider, Request

from scrapy_playwright.handler import PERSISTENT_CONTEXT_NAME

from tests import make_handler
from tests.mockserver import StaticMockServer


class MixinTestCaseMultipleContexts:
    @pytest.mark.asyncio
    async def test_contexts_max_pages_setting(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1234,
        }
        async with make_handler(settings) as handler:
            assert handler.max_pages_per_context == 1234

        settings = {"PLAYWRIGHT_BROWSER_TYPE": self.browser_type, "CONCURRENT_REQUESTS": 9876}
        async with make_handler(settings) as handler:
            assert handler.max_pages_per_context == 9876

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
            assert len(handler.contexts) == 1

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
            await page.context.close()
            await page.close()
            cookie = storage_state["cookies"][0]
            assert cookie["name"] == "foo"
            assert cookie["value"] == "bar"
            assert cookie["domain"] == "example.org"

    @pytest.mark.asyncio
    async def test_persistent_context(self, caplog):
        temp_dir = f"{tempfile.gettempdir()}/{uuid4()}"
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 3000,
            "PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS": {
                "user_data_dir": temp_dir,
            },
            "PLAYWRIGHT_CONTEXTS": {
                "foo": {},
            },
        }
        assert not Path(temp_dir).exists()
        async with make_handler(settings) as handler:
            assert handler.persistent_context
            assert Path(temp_dir).is_dir()
            assert PERSISTENT_CONTEXT_NAME in handler.contexts
            assert len(handler.contexts) == 1
            assert getattr(handler, "browser", None) is None

            with StaticMockServer() as server:
                meta = {
                    "playwright": True,
                    "playwright_context": "will-be-ignored",
                }
                req = Request(server.urljoin("/index.html"), meta=meta)
                resp = await handler._download_request(req, Spider("foo"))
                assert resp.meta["playwright_context"] == PERSISTENT_CONTEXT_NAME

                assert (
                    "scrapy-playwright",
                    logging.WARNING,
                    "Both PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS and PLAYWRIGHT_CONTEXTS"
                    " are set, ignoring PLAYWRIGHT_CONTEXTS",
                ) in caplog.record_tuples

    @pytest.mark.asyncio
    async def test_contexts_dynamic(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:
            assert len(handler.contexts) == 0

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

            assert len(handler.contexts) == 1

            page = resp.meta["playwright_page"]
            storage_state = await page.context.storage_state()
            await page.close()
            cookie = storage_state["cookies"][0]
            assert cookie["name"] == "asdf"
            assert cookie["value"] == "qwerty"
            assert cookie["domain"] == "example.org"


class TestCaseMultipleContextsChromium(MixinTestCaseMultipleContexts):
    browser_type = "chromium"


class TestCaseMultipleContextsFirefox(MixinTestCaseMultipleContexts):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseMultipleContextsWebkit(MixinTestCaseMultipleContexts):
    browser_type = "webkit"
