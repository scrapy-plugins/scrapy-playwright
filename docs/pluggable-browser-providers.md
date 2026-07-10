# Pluggable browser providers

Third-party projects such as [patchright](https://pypi.org/project/patchright/),
[camoufox](https://pypi.org/project/camoufox/), and
[invisible_playwright](https://github.com/feder-cr/invisible_playwright) provide
drop-in replacements for Playwright's browser startup while keeping standard
`Browser`/`BrowserContext`/`Page` objects. Because those objects are unchanged,
pages, contexts and routing code keeps working — only how the browser is
started and stopped differs.

scrapy-playwright exposes a single extension point for this: the
`PLAYWRIGHT_BROWSER_PROVIDER` setting. It takes the import path of a *browser
provider* — a class that owns the browser lifecycle. The built-in provider wraps
vanilla Playwright; you can integrate any other backend by pointing the setting
at your own provider class.

## The `PLAYWRIGHT_BROWSER_PROVIDER` setting

Type `str` or `type`, default `"scrapy_playwright.provider.PlaywrightBrowserProvider"`.

```python
# settings.py
PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.CustomBrowserProvider"
```

The value may be either an import path string or the provider class directly. The
class is instantiated with a configuration object (see
[Reading configuration](#reading-configuration)) and drives every browser that
scrapy-playwright uses. When the setting is not set, the built-in
`PlaywrightBrowserProvider` is used.

## The `BrowserProvider` interface

A provider is a class that accepts a configuration object in its constructor and
implements the following asynchronous lifecycle. You can subclass
`scrapy_playwright.provider.BrowserProvider` (a `typing.Protocol`) to document
the intent, but it is not required — any class with these methods works.

```python
from playwright.async_api import Browser, BrowserContext
from scrapy.exceptions import NotSupported
from scrapy_playwright.handler import Config


class BrowserProvider:
    def __init__(self, config: Config) -> None:
        ...

    async def start(self) -> None:
        """Perform any one-time initialization.

        Called once before the first browser is requested. Providers that create
        their browser on demand can leave this empty.
        """

    async def launch_browser(self) -> Browser:
        """Return a launched or connected Playwright-compatible ``Browser``.

        Called when a browser is needed, and again if the previous browser
        disconnects and ``PLAYWRIGHT_RESTART_DISCONNECTED_BROWSER`` is enabled.
        """

    async def launch_persistent_context(self, context_kwargs: dict) -> BrowserContext:
        """Return a persistent ``BrowserContext``.

        Called when a context requests a ``user_data_dir``. Raise
        ``scrapy.exceptions.NotSupported`` if the backend has no equivalent.
        """
        raise NotSupported("This provider does not support persistent contexts")

    async def close(self) -> None:
        """Release any resources acquired in ``start`` / ``launch_browser``.

        Awaited once when the crawl finishes.
        """
```

Import any optional third-party library lazily (inside the methods that need
it), so the setting can point at a provider whose backend is only installed in
some environments without affecting others.

## Reading configuration

The object passed to the constructor exposes the resolved Playwright settings as
attributes, so a provider can honor them. The most commonly used are:

| Attribute | Setting |
|---|---|
| `browser_type_name` | `PLAYWRIGHT_BROWSER_TYPE` |
| `launch_options` | `PLAYWRIGHT_LAUNCH_OPTIONS` |
| `cdp_url` / `cdp_kwargs` | `PLAYWRIGHT_CDP_URL` / `PLAYWRIGHT_CDP_KWARGS` |
| `connect_url` / `connect_kwargs` | `PLAYWRIGHT_CONNECT_URL` / `PLAYWRIGHT_CONNECT_KWARGS` |

## Built-in provider

`scrapy_playwright.provider.PlaywrightBrowserProvider` is the default provider. It wraps
vanilla Playwright and supports the full feature set documented in the README: launching a local
browser, connecting to a remote one through `PLAYWRIGHT_CDP_URL` or `PLAYWRIGHT_CONNECT_URL`,
and persistent contexts. Custom providers below follow the same interface.

## About the examples

The examples that follow are provided **only as guidelines** to illustrate how a
custom provider can be structured; they are not part of scrapy-playwright and are
not officially supported extensions. They may be incomplete or become outdated as
the third-party libraries evolve — treat them as a starting point and adapt them
as needed.

scrapy-playwright is **not affiliated with, endorsed by, or otherwise connected
to** any of the third-party projects mentioned here (patchright, camoufox,
invisible_playwright, or any other). They are referenced purely as examples of
Playwright-compatible backends. Refer to each project's own documentation and
license for authoritative, up-to-date usage, and evaluate any third-party
dependency yourself before using it.

## Example: patchright

Patchright mirrors the Playwright async API (Chromium only), so a provider can
use it exactly like Playwright, including persistent contexts.

```python
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
```

```python
# settings
PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.PatchrightBrowserProvider"
PLAYWRIGHT_BROWSER_TYPE = "chromium"
```

## Example: camoufox

`AsyncCamoufox` is an async context manager that yields a `Browser` directly, or
a persistent `BrowserContext` when passed `persistent_context=True` and a
`user_data_dir`. It is Firefox-based, so set `PLAYWRIGHT_BROWSER_TYPE = "firefox"`.

```python
from contextlib import AsyncExitStack

from scrapy_playwright.handler import Config, PERSISTENT_CONTEXT_PATH_KEY


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
```

```python
# settings
PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.CamoufoxBrowserProvider"
PLAYWRIGHT_BROWSER_TYPE = "firefox"
```

## Example: invisible_playwright

Same shape as camoufox — `InvisiblePlaywright(...)` is an async context manager
yielding a standard `playwright.async_api.Browser`, or a persistent
`BrowserContext` when passed a `profile_dir`. Firefox-based, so set
`PLAYWRIGHT_BROWSER_TYPE = "firefox"`.

```python
from contextlib import AsyncExitStack

from scrapy_playwright.handler import Config, PERSISTENT_CONTEXT_PATH_KEY


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
```

```python
# settings
PLAYWRIGHT_BROWSER_PROVIDER = "myproject.providers.InvisibleBrowserProvider"
PLAYWRIGHT_BROWSER_TYPE = "firefox"
```
