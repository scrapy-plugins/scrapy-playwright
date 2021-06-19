import platform

import pytest
from scrapy import Spider, Request
from scrapy.utils.test import get_crawler

from scrapy_playwright.handler import ScrapyPlaywrightDownloadHandler

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
        handler = ScrapyPlaywrightDownloadHandler(get_crawler(settings_dict=settings))
        await handler._launch_browser()

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
        cookie = storage_state["cookies"][0]
        assert cookie["name"] == "foo"
        assert cookie["value"] == "bar"
        assert cookie["domain"] == "example.org"

        await page.close()
        await handler.browser.close()

    @pytest.mark.asyncio
    async def test_contexts_dynamic(self):
        settings = {"PLAYWRIGHT_BROWSER_TYPE": self.browser_type}
        handler = ScrapyPlaywrightDownloadHandler(get_crawler(settings_dict=settings))
        await handler._launch_browser()

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
        cookie = storage_state["cookies"][0]
        assert cookie["name"] == "asdf"
        assert cookie["value"] == "qwerty"
        assert cookie["domain"] == "example.org"

        await page.close()
        await handler.browser.close()


class TestCaseMultipleContextsChromium(MixinTestCaseMultipleContexts):
    browser_type = "chromium"


class TestCaseMultipleContextsFirefox(MixinTestCaseMultipleContexts):
    browser_type = "firefox"


@pytest.mark.skipif(platform.system() != "Darwin", reason="Test WebKit only on Darwin")
class TestCaseMultipleContextsWebkit(MixinTestCaseMultipleContexts):
    browser_type = "webkit"
