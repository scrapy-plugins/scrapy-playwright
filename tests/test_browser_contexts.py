import platform
import warnings

import pytest
from scrapy import Spider, Request

from tests import make_handler
from tests.mockserver import StaticMockServer


class MixinTestCaseMultipleContexts:
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
    async def test_contexts_dynamic(self):
        async with make_handler({"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}) as handler:

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

            page = resp.meta["playwright_page"]
            storage_state = await page.context.storage_state()
            await page.close()
            cookie = storage_state["cookies"][0]
            assert cookie["name"] == "asdf"
            assert cookie["value"] == "qwerty"
            assert cookie["domain"] == "example.org"

    @pytest.mark.asyncio
    async def test_deprecated_setting(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": self.browser_type,
            "PLAYWRIGHT_CONTEXT_ARGS": {
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
        with warnings.catch_warnings(record=True) as warning_list:
            async with make_handler(settings) as handler:
                assert warning_list[0].category is DeprecationWarning
                assert str(warning_list[0].message) == (
                    "The PLAYWRIGHT_CONTEXT_ARGS setting is deprecated, please use"
                    " PLAYWRIGHT_CONTEXTS instead. Keyword arguments defined in"
                    " PLAYWRIGHT_CONTEXT_ARGS will be used when creating the 'default' context"
                )

                with StaticMockServer() as server:
                    meta = {
                        "playwright": True,
                        "playwright_include_page": True,
                    }
                    req = Request(server.urljoin("/index.html"), meta=meta)
                    resp = await handler._download_request(req, Spider("foo"))

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
