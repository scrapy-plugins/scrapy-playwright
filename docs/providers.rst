.. _providers:

===========================
Pluggable browser providers
===========================

Third-party projects such as `patchright
<https://pypi.org/project/patchright/>`__, `camoufox
<https://pypi.org/project/camoufox/>`__ and `invisible_playwright
<https://github.com/feder-cr/invisible_playwright>`__ provide drop-in
replacements for the browser startup of Playwright, while keeping standard
``Browser``, ``BrowserContext`` and ``Page`` objects. Because those objects are
unchanged, pages, contexts and routing code keep working; only how the browser
is started and stopped differs.

The :setting:`PLAYWRIGHT_BROWSER_PROVIDER` setting is the extension point for
that. It takes a *browser provider*, a class that owns the browser lifecycle
and drives every browser that scrapy-playwright uses.


The provider interface
======================

A provider is a class that takes a configuration object in its constructor and
implements the asynchronous lifecycle of
:class:`~scrapy_playwright.provider.BrowserProvider`. Subclassing that
:class:`~typing.Protocol` documents the intent, but any class with those
methods works.

Import any optional third-party library lazily, inside the methods that need
it, so that the setting can point at a provider whose backend is only
installed in some environments.

The configuration object exposes the resolved Playwright settings as
attributes, so that a provider can honor them. The most commonly used are:

-   ``browser_type_name``, from :setting:`PLAYWRIGHT_BROWSER_TYPE`.

-   ``launch_options``, from :setting:`PLAYWRIGHT_LAUNCH_OPTIONS`.

-   ``cdp_url`` and ``cdp_kwargs``, from :setting:`PLAYWRIGHT_CDP_URL` and
    :setting:`PLAYWRIGHT_CDP_KWARGS`.

-   ``connect_url`` and ``connect_kwargs``, from
    :setting:`PLAYWRIGHT_CONNECT_URL` and :setting:`PLAYWRIGHT_CONNECT_KWARGS`.


Examples
========

The providers below are guidelines that illustrate how a custom provider can
be structured. They are not part of scrapy-playwright, and they are not
officially supported extensions. They may be incomplete or become outdated as
the third-party libraries evolve, so treat them as a starting point and adapt
them as needed.

scrapy-playwright is not affiliated with, endorsed by, or otherwise connected
to any of the third-party projects mentioned here. They are referenced purely
as examples of Playwright-compatible backends. Refer to the documentation and
the license of each project for authoritative, up-to-date usage, and evaluate
any third-party dependency yourself before using it.


patchright
----------

Patchright mirrors the asynchronous Playwright API, for Chromium only, so a
provider can use it exactly like Playwright, including persistent contexts.

.. code-block:: python

    from contextlib import AsyncExitStack

    from scrapy_playwright.handler import Config


    class PatchrightBrowserProvider:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.stack = AsyncExitStack()
            self.browser_type: BrowserType

        async def start(self) -> None:
            from patchright.async_api import async_playwright

            _patchright = await self.stack.enter_async_context(async_playwright())
            self.browser_type = _patchright.chromium

        async def launch_browser(self):
            return await self.browser_type.launch(**self.config.launch_options)

        async def launch_persistent_context(self, context_kwargs: dict):
            return await self.browser_type.launch_persistent_context(**context_kwargs)

        async def close(self) -> None:
            await self.stack.aclose()

.. code-block:: python

    # settings.py
    PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.PatchrightBrowserProvider"
    PLAYWRIGHT_BROWSER_TYPE = "chromium"


camoufox
--------

``AsyncCamoufox`` is an asynchronous context manager that yields a ``Browser``
directly, or a persistent ``BrowserContext`` when passed
``persistent_context=True`` and a ``user_data_dir``. It is Firefox-based.

.. code-block:: python

    from contextlib import AsyncExitStack

    from scrapy_playwright.handler import PERSISTENT_CONTEXT_PATH_KEY, Config


    class CamoufoxBrowserProvider:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.stack = AsyncExitStack()

        async def start(self) -> None:
            pass

        async def launch_browser(self):
            from camoufox.async_api import AsyncCamoufox

            return await self.stack.enter_async_context(
                AsyncCamoufox(**self.config.launch_options)
            )

        async def launch_persistent_context(self, context_kwargs: dict):
            from camoufox.async_api import AsyncCamoufox

            return await self.stack.enter_async_context(
                AsyncCamoufox(
                    persistent_context=True,
                    user_data_dir=context_kwargs[PERSISTENT_CONTEXT_PATH_KEY],
                    **self.config.launch_options,
                )
            )

        async def close(self) -> None:
            await self.stack.aclose()

.. code-block:: python

    # settings.py
    PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.CamoufoxBrowserProvider"
    PLAYWRIGHT_BROWSER_TYPE = "firefox"


invisible_playwright
--------------------

``InvisiblePlaywright`` is an asynchronous context manager that yields a
standard ``playwright.async_api.Browser``, or a persistent ``BrowserContext``
when passed a ``profile_dir``. It is Firefox-based.

.. code-block:: python

    from contextlib import AsyncExitStack

    from scrapy_playwright.handler import PERSISTENT_CONTEXT_PATH_KEY, Config


    class InvisibleBrowserProvider:
        def __init__(self, config: Config) -> None:
            self.config = config
            self.stack = AsyncExitStack()

        async def start(self) -> None:
            pass

        async def launch_browser(self):
            from invisible_playwright.async_api import InvisiblePlaywright

            # e.g. seed / proxy / timezone / pin via PLAYWRIGHT_LAUNCH_OPTIONS
            return await self.stack.enter_async_context(
                InvisiblePlaywright(**self.config.launch_options)
            )

        async def launch_persistent_context(self, context_kwargs: dict):
            from invisible_playwright.async_api import InvisiblePlaywright

            # invisible_playwright names the profile path ``profile_dir``
            return await self.stack.enter_async_context(
                InvisiblePlaywright(
                    profile_dir=context_kwargs[PERSISTENT_CONTEXT_PATH_KEY],
                    **self.config.launch_options,
                )
            )

        async def close(self) -> None:
            await self.stack.aclose()

.. code-block:: python

    # settings.py
    PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.InvisibleBrowserProvider"
    PLAYWRIGHT_BROWSER_TYPE = "firefox"
