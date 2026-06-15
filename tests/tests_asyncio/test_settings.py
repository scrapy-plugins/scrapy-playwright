from unittest import TestCase

import pytest
from scrapy.exceptions import NotSupported
from scrapy.settings import Settings

from scrapy_playwright.handler import Config

from tests import create_handler


class TestSettings(TestCase):
    def test_settings_timeout_value(self):
        config = Config.from_settings(Settings({}))
        assert config.navigation_timeout_ms is None

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": None}))
        assert config.navigation_timeout_ms is None

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0}))
        assert config.navigation_timeout_ms == 0

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 123}))
        assert config.navigation_timeout_ms == 123

        config = Config.from_settings(Settings({"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 0.5}))
        assert config.navigation_timeout_ms == 0.5

    def test_max_pages_per_context(self):
        config = Config.from_settings(Settings({"PLAYWRIGHT_MAX_PAGES_PER_CONTEXT": 1234}))
        assert config.max_pages_per_context == 1234

        config = Config.from_settings(Settings({"CONCURRENT_REQUESTS": 9876}))
        assert config.max_pages_per_context == 9876

    def test_connect_remote_urls(self):
        with pytest.raises(NotSupported) as exc_info:
            Config.from_settings(
                Settings({"PLAYWRIGHT_CONNECT_URL": "asdf", "PLAYWRIGHT_CDP_URL": "qwerty"})
            )
        assert (
            str(exc_info.value)
            == "Setting both PLAYWRIGHT_CDP_URL and PLAYWRIGHT_CONNECT_URL is not supported"
        )

    def test_max_contexts(self):
        handler = create_handler({"PLAYWRIGHT_MAX_CONTEXTS": None})
        assert not hasattr(handler, "context_semaphore")

        handler = create_handler({"PLAYWRIGHT_MAX_CONTEXTS": 1234})
        assert handler.context_semaphore._value == 1234
