from unittest import IsolatedAsyncioTestCase

from scrapy.settings import Settings

from scrapy_playwright.handler import Config

from tests import allow_windows, make_handler


class TestSettings(IsolatedAsyncioTestCase):
    async def test_settings_timeout_value(self):
        config = Config.from_settings(Settings({}))
        assert config.navigation_timeout is None

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": None}))
        assert config.navigation_timeout is None

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0}))
        assert config.navigation_timeout == 0

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 123}))
        assert config.navigation_timeout == 123

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0.5}))
        assert config.navigation_timeout == 0.5

    async def test_max_pages_per_context(self):
        config = Config.from_settings(Settings({"PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1234}))
        assert config.max_pages_per_context == 1234

        config = Config.from_settings(Settings({"CONCURRENT_REQUESTS": 9876}))
        assert config.max_pages_per_context == 9876

    @allow_windows
    async def test_max_contexts(self):
        async with make_handler({"PLAYWRIGHT_MAX_CONTEXTS": None}) as handler:
            assert not hasattr(handler, "context_semaphore")

        async with make_handler({"PLAYWRIGHT_MAX_CONTEXTS": 1234}) as handler:
            assert handler.context_semaphore._value == 1234
