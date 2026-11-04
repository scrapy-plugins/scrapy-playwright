from unittest import TestCase

import pytest
from scrapy.settings import Settings

AddonManager = pytest.importorskip("scrapy.addons").AddonManager

_HANDLER = "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler"


def _settings(**kwargs) -> Settings:
    settings = Settings({"ADDONS": {"scrapy_playwright.Addon": 100}, **kwargs})
    AddonManager(crawler=None).load_settings(settings)
    return settings


class TestAddon(TestCase):
    def test_enables_handlers_and_reactor(self):
        settings = _settings()
        handlers = settings.getwithbase("DOWNLOAD_HANDLERS")
        assert handlers["http"] == _HANDLER
        assert handlers["https"] == _HANDLER
        assert (
            settings["TWISTED_REACTOR"] == "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
        )

    def test_keeps_user_defined_handlers(self):
        settings = _settings(DOWNLOAD_HANDLERS={"https": "some.custom.Handler"})
        handlers = settings.getwithbase("DOWNLOAD_HANDLERS")
        assert handlers["http"] == _HANDLER
        assert handlers["https"] == "some.custom.Handler"
