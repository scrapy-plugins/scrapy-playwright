import tempfile
from typing import Optional
from unittest import IsolatedAsyncioTestCase, TestCase
from uuid import uuid4

import pytest
from playwright.async_api import Browser, PlaywrightContextManager, async_playwright
from scrapy import Request, Spider
from scrapy.exceptions import NotSupported
from scrapy.settings import Settings

from scrapy_playwright.handler import Config
from scrapy_playwright.provider import BrowserProvider, PlaywrightBrowserProvider

from tests import (
    allow_windows,
    assert_correct_response,
    create_handler,
    make_handler,
    BaseTestCase,
)


class CustomBrowserProvider:
    """A standalone provider (not subclassing the default) that yields a real
    Playwright ``Browser``, mirroring how a third-party driver would integrate:
    it enters an async context manager and returns the browser it produces.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._cm: Optional[PlaywrightContextManager] = None
        self.started = False
        self.launched = False

    async def start(self) -> None:
        self.started = True

    async def launch_browser(self) -> Browser:
        self.launched = True
        self._cm = async_playwright()
        playwright = await self._cm.__aenter__()
        browser_type = getattr(playwright, self.config.browser_type_name)
        return await browser_type.launch(**self.config.launch_options)

    async def launch_persistent_context(self, context_kwargs: dict):
        raise NotSupported("CustomBrowserProvider does not support persistent contexts")

    async def close(self) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)


class TestProviderSetting(TestCase):
    def test_default_provider_class(self):
        handler = create_handler({})
        assert handler.browser_provider_cls is PlaywrightBrowserProvider

    def test_default_provider_class_when_empty(self):
        handler = create_handler({"PLAYWRIGHT_BROWSER_PROVIDER": ""})
        assert handler.browser_provider_cls is PlaywrightBrowserProvider

    def test_custom_provider_class_loaded(self):
        handler = create_handler({"PLAYWRIGHT_BROWSER_PROVIDER": CustomBrowserProvider})
        assert handler.browser_provider_cls is CustomBrowserProvider

    def test_default_provider_implements_protocol(self):
        assert isinstance(
            PlaywrightBrowserProvider(Config.from_settings(Settings({}))), BrowserProvider
        )


class TestPlaywrightBrowserProvider(IsolatedAsyncioTestCase):
    @allow_windows
    async def test_launch_before_start_raises(self):
        provider = PlaywrightBrowserProvider(Config.from_settings(Settings({})))
        with pytest.raises(
            RuntimeError, match="start\\(\\) must be awaited before launch_browser"
        ):
            await provider.launch_browser()
        with pytest.raises(
            RuntimeError, match="start\\(\\) must be awaited before launch_persistent_context"
        ):
            await provider.launch_persistent_context({})

    @allow_windows
    async def test_lifecycle(self):
        config = Config.from_settings(
            Settings(
                {
                    "PLAYWRIGHT_BROWSER_TYPE": "chromium",
                    "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
                }
            )
        )
        provider = PlaywrightBrowserProvider(config)
        await provider.start()
        assert provider.browser_type is not None
        assert provider.browser_type.name == "chromium"
        browser = await provider.launch_browser()
        try:
            assert isinstance(browser, Browser)
            assert browser.is_connected()
        finally:
            await browser.close()
            await provider.close()


class TestCustomProvider(IsolatedAsyncioTestCase, BaseTestCase):
    @allow_windows
    async def test_custom_provider_used_end_to_end(self):
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_BROWSER_PROVIDER": CustomBrowserProvider,
            "PLAYWRIGHT_LAUNCH_OPTIONS": {"headless": True},
        }
        async with make_handler(settings) as handler:
            assert isinstance(handler.browser_provider, CustomBrowserProvider)
            assert handler.browser_provider.started
            req = Request(self.static_server.urljoin("/index.html"), meta={"playwright": True})
            resp = await handler._download_request(req, Spider("foo"))
            assert_correct_response(resp, req)
            assert handler.browser_provider.launched
            assert isinstance(handler.browser, Browser)

    @allow_windows
    async def test_persistent_context_not_supported(self):
        temp_dir = f"{tempfile.gettempdir()}/{uuid4()}"
        settings = {
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_BROWSER_PROVIDER": CustomBrowserProvider,
        }
        async with make_handler(settings) as handler:
            req = Request(
                self.static_server.urljoin("/index.html"),
                meta={
                    "playwright": True,
                    "playwright_context": "persistent",
                    "playwright_context_kwargs": {"user_data_dir": temp_dir},
                },
            )
            with pytest.raises(NotSupported):
                await handler._download_request(req, Spider("foo"))
