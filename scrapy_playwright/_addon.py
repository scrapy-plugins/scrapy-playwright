from scrapy.settings import BaseSettings


class Addon:
    """Scrapy add-on that enables scrapy-playwright.

    It sets the ``http`` and ``https`` download handlers, and the
    ``asyncio``-based Twisted reactor that they require.
    """

    def update_settings(self, settings: BaseSettings) -> None:
        for scheme in ("http", "https"):
            settings["DOWNLOAD_HANDLERS"].set(
                scheme,
                "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "addon",
            )
        settings.set(
            "TWISTED_REACTOR",
            "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "addon",
        )
