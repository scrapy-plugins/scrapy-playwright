"""Pluggable browser providers.

A browser provider owns the browser lifecycle: startup, producing
launched/connected :class:`~playwright.async_api.Browser` objects, optionally
producing persistent contexts, and teardown. The download handler delegates to
the provider configured via the ``PLAYWRIGHT_BROWSER_PROVIDER`` setting (an import
path or class), defaulting to :class:`PlaywrightBrowserProvider`.

Third-party drivers that expose Playwright-compatible ``Browser`` objects (e.g.
patchright, camoufox) can be integrated by implementing a provider, without any
driver-specific code living in the handler. See
``docs/pluggable-browser-providers.md``.
"""

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from playwright.async_api import (
    Browser,
    BrowserContext,
    BrowserType,
    Playwright as AsyncPlaywright,
    PlaywrightContextManager,
)

from scrapy_playwright.handler import logger

if TYPE_CHECKING:
    from scrapy_playwright.handler import Config


__all__ = ["BrowserProvider", "PlaywrightBrowserProvider"]


@runtime_checkable
class BrowserProvider(Protocol):
    """Interface expected of ``PLAYWRIGHT_BROWSER_PROVIDER`` implementations.

    Instances receive a :class:`~scrapy_playwright.handler.Config` object as argument
    to their __init__ method. All methods are coroutines and are awaited by the handler.
    """

    def __init__(self, config: "Config") -> None: ...

    async def start(self) -> None:
        """One-time initialization, awaited once when the handler launches."""

    async def launch_browser(self) -> Browser:
        """Return a launched or connected Playwright-compatible ``Browser``.

        Called (behind a lock) the first time a browser is needed, and again after a
        disconnection if ``PLAYWRIGHT_RESTART_DISCONNECTED_BROWSER`` is enabled.
        """

    async def launch_persistent_context(self, context_kwargs: dict) -> BrowserContext:
        """Return a persistent context (a ``user_data_dir`` was requested).

        Providers whose backend has no equivalent should raise
        :class:`scrapy.exceptions.NotSupported`.
        """

    async def close(self) -> None:
        """Tear down any allocated resources. Awaited once when the handler shuts down."""


class PlaywrightBrowserProvider:
    """Default provider, wrapping vanilla Playwright.

    Encapsulates the browser lifecycle: it starts a
    :class:`~playwright.async_api.PlaywrightContextManager`, resolves the
    configured browser type, and launches locally or connects to a remote
    browser (``PLAYWRIGHT_CDP_URL`` / ``PLAYWRIGHT_CONNECT_URL``) as needed.
    """

    def __init__(self, config: "Config") -> None:
        self.config = config
        self.playwright_context_manager: Optional[PlaywrightContextManager] = None
        self.playwright: Optional[AsyncPlaywright] = None
        self.browser_type: Optional[BrowserType] = None

    async def start(self) -> None:
        self.playwright_context_manager = PlaywrightContextManager()
        self.playwright = await self.playwright_context_manager.start()
        self.browser_type = getattr(self.playwright, self.config.browser_type_name)

    async def launch_browser(self) -> Browser:
        if self.browser_type is None:
            raise RuntimeError("start() must be awaited before launch_browser()")
        if self.config.cdp_url:
            logger.info("Connecting using CDP: %s", self.config.cdp_url)
            browser = await self.browser_type.connect_over_cdp(
                self.config.cdp_url, **self.config.cdp_kwargs
            )
            logger.info("Connected using CDP: %s", self.config.cdp_url)
        elif self.config.connect_url:
            logger.info("Connecting to remote Playwright")
            browser = await self.browser_type.connect(
                self.config.connect_url, **self.config.connect_kwargs
            )
            logger.info("Connected to remote Playwright")
        else:
            logger.info("Launching browser %s", self.browser_type.name)
            browser = await self.browser_type.launch(**self.config.launch_options)
            logger.info("Browser %s launched", self.browser_type.name)
        return browser

    async def launch_persistent_context(self, context_kwargs: dict) -> BrowserContext:
        if self.browser_type is None:
            raise RuntimeError("start() must be awaited before launch_persistent_context()")
        return await self.browser_type.launch_persistent_context(**context_kwargs)

    async def close(self) -> None:
        if self.playwright_context_manager:
            await self.playwright_context_manager.__aexit__()
        if self.playwright:
            await self.playwright.stop()
