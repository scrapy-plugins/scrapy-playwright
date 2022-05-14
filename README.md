# scrapy-playwright: Playwright integration for Scrapy
[![version](https://img.shields.io/pypi/v/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![pyversions](https://img.shields.io/pypi/pyversions/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![Tests](https://github.com/scrapy-plugins/scrapy-playwright/actions/workflows/tests.yml/badge.svg)](https://github.com/scrapy-plugins/scrapy-playwright/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/scrapy-plugins/scrapy-playwright/branch/master/graph/badge.svg)](https://codecov.io/gh/scrapy-plugins/scrapy-playwright)


A Scrapy Download Handler which performs requests using
[Playwright for Python](https://github.com/microsoft/playwright-python).
It can be used to handle pages that require JavaScript (among other things),
while adhering to the regular Scrapy workflow (i.e. without interfering
with request scheduling, item processing, etc).


## Requirements

After the release of [version 2.0](https://docs.scrapy.org/en/latest/news.html#scrapy-2-0-0-2020-03-03),
which includes [coroutine syntax support](https://docs.scrapy.org/en/2.0/topics/coroutines.html)
and [asyncio support](https://docs.scrapy.org/en/2.0/topics/asyncio.html), Scrapy allows
to integrate `asyncio`-based projects such as `Playwright`.


### Minimum required versions

* Python >= 3.7
* Scrapy >= 2.0 (!= 2.4.0)
* Playwright >= 1.15


## Installation

```
$ pip install scrapy-playwright
```

## Changelog

Please see the [changelog.md](changelog.md) file.


## Activation

Replace the default `http` and/or `https` Download Handlers through
[`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html):

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
```

Note that the `ScrapyPlaywrightDownloadHandler` class inherits from the default
`http/https` handler. Unless explicitly marked (see the "Basic usage"),
requests will be processed by the regular Scrapy download handler.

Also, be sure to [install the `asyncio`-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor):

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

## Settings

`scrapy-playwright` accepts the following settings:

* `PLAYWRIGHT_BROWSER_TYPE` (type `str`, default `chromium`)
    The browser type to be launched, e.g. `chromium`, `firefox`, `webkit`.

* `PLAYWRIGHT_LAUNCH_OPTIONS` (type `dict`, default `{}`)

    A dictionary with options to be passed when launching the Browser.
    See the docs for [`BrowserType.launch`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch).

* `PLAYWRIGHT_CONTEXTS` (type `dict[str, dict]`, default `{}`)

    A dictionary which defines Browser contexts to be created on startup.
    It should be a mapping of (name, keyword arguments). For instance:
    ```python
    {
        "first": {
            "context_arg1": "value",
            "context_arg2": "value",
        },
        "second": {
            "context_arg1": "value",
        },
    }
    ```
    A default context (called `default`) is created if no contexts are defined,
    this will be used by all requests which do not explicitly specify a context.
    See the docs for [`Browser.new_context`](https://playwright.dev/python/docs/api/class-browser#browser-new-context).

* `PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS` (type `Optional[dict]`, default `None`)

    A dictionary of keyword arguments to be passed to
    [`BrowserType.launch_persistent_context`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).
    Use this setting to launch a **single** persistent context.
    This setting takes precedence over `PLAYWRIGHT_CONTEXTS`,
    i.e. `PLAYWRIGHT_CONTEXTS` is ignored if both are passed.

* `PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT` (type `Optional[float]`, default `None`)

    The timeout used when requesting pages by Playwright. If `None` or unset,
    the default value will be used (30000 ms at the time of writing this).
    See the docs for [BrowserContext.set_default_navigation_timeout](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-set-default-navigation-timeout).

* `PLAYWRIGHT_PROCESS_REQUEST_HEADERS` (type `Optional[Union[Callable, str]]`, default `scrapy_playwright.headers.use_scrapy_headers`)

    A function (or the path to a function) that processes headers for a given request
    and returns a dictionary with the headers to be used (note that, depending on the browser,
    additional default headers could be sent as well). Coroutine functions (`async def`) are
    supported.

    This will be called at least once for each Scrapy request (receiving said request and the
    corresponding Playwright request), but it could be called additional times if the given
    resource generates more requests (e.g. to retrieve assets like images or scripts).

    The function must return a `dict` object, and receives the following keyword arguments:

    ```python
    - browser_type: str
    - playwright_request: playwright.async_api.Request
    - scrapy_headers: scrapy.http.headers.Headers
    ```

    The default value (`scrapy_playwright.headers.use_scrapy_headers`) tries to emulate Scrapy's
    behaviour for navigation requests, i.e. overriding headers with their values from the Scrapy request.
    For non-navigation requests (e.g. images, stylesheets, scripts, etc), only the `User-Agent` header
    is overriden, for consistency.

    Setting `PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None` will give complete control of the headers to
    Playwright, i.e. headers from Scrapy requests will be ignored and only headers set by
    Playwright will be sent.
    When doing this, please keep in mind that headers passed via the `Request.headers` attribute
    or set by Scrapy components are ignored (including cookies set via the `Request.cookies`
    attribute).

* `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` (type `int`, defaults to the value of Scrapy's `CONCURRENT_REQUESTS` setting)

    Maximum amount of allowed concurrent Playwright pages for each context.
    See the [notes about leaving unclosed pages](#receiving-the-page-object-in-the-callback).

* `PLAYWRIGHT_ABORT_REQUEST` (type `Optional[Union[Callable, str]]`, default `None`)

    A predicate function (or the path to a function) that receives a
    `playwright.async_api.Request` object and must return `True` if the
    request should be aborted, `False` otherwise. Coroutine functions
    (`async def`) are supported.

    For instance, the following are all equivalent, and prevent the download of images:
    ```python
    PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type == "image"
    ```

    ```python
    def should_abort_request(req):
        return req.resource_type == "image"

    PLAYWRIGHT_ABORT_REQUEST = should_abort_request
    ```

    ```python
    # project/utils.py
    def should_abort_request(req):
        return req.resource_type == "image"

    # settings.py
    PLAYWRIGHT_ABORT_REQUEST = "project.utils.should_abort_request"

    ```

    Please note that all requests will appear in the DEBUG level logs, however there will
    be no corresponding response log lines for aborted requests. Aborted requests
    are counted in the `playwright/request_count/aborted` job stats item.

    ### General note about settings

    For the settings which accept object paths as strings, passing callable objects is
    only supported when using Scrapy>=2.4. With prior versions, only strings are supported.


## Basic usage

Set the `playwright` [Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
key to download a request using Playwright:

```python
import scrapy

class AwesomeSpider(scrapy.Spider):
    name = "awesome"

    def start_requests(self):
        # GET request
        yield scrapy.Request("https://httpbin.org/get", meta={"playwright": True})
        # POST request
        yield scrapy.FormRequest(
            url="https://httpbin.org/post",
            formdata={"foo": "bar"},
            meta={"playwright": True},
        )

    def parse(self, response):
        # 'response' contains the page as seen by the browser
        yield {"url": response.url}
```

### Notes about the User-Agent header

By default, outgoing requests include the `User-Agent` set by Scrapy (either with the
`USER_AGENT` or `DEFAULT_REQUEST_HEADERS` settings or via the `Request.headers` attribute).
This could cause some sites to react in unexpected ways, for instance if the user agent
does not match the running Browser. If you prefer the `User-Agent` sent by
default by the specific browser you're using, set the Scrapy user agent to `None`.


## Receiving Page objects in callbacks

Specifying a non-False value for the `playwright_include_page` `meta` key for a
request will result in the corresponding `playwright.async_api.Page` object
being available in the `playwright_page` meta key in the request callback.
In order to be able to `await` coroutines on the provided `Page` object,
the callback needs to be defined as a coroutine function (`async def`).

```python
import scrapy

class AwesomeSpiderWithPage(scrapy.Spider):
    name = "page"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta={"playwright": True, "playwright_include_page": True},
            errback=self.errback,
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        title = await page.title()  # "Example Domain"
        await page.close()
        return {"title": title}

    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()
```

**Notes:**

* In order to avoid memory issues, it is recommended to manually close the page
  by awaiting the `Page.close` coroutine.
* Be careful about leaving pages unclosed, as they count towards the limit set by
  `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT`. When passing `playwright_include_page=True`,
  it's recommended to set a Request errback to make sure pages are closed even
  if a request fails (if `playwright_include_page=False` or unset, pages are
  automatically closed upon encountering an exception).
* Any network operations resulting from awaiting a coroutine on a `Page` object
  (`goto`, `go_back`, etc) will be executed directly by Playwright, bypassing the
  Scrapy request workflow (Scheduler, Middlewares, etc).


## Multiple browser contexts

Multiple [browser contexts](https://playwright.dev/python/docs/browser-contexts)
to be launched at startup can be defined via the `PLAYWRIGHT_CONTEXTS` [setting](#settings).

**Note:** this section doesn not apply if using the
`PLAYWRIGHT_PERSISTENT_CONTEXT_KWARGS` setting. In that case,
only one context is used for all operations.

### Choosing a specific context for a request

Pass the name of the desired context in the `playwright_context` meta key:

```python
yield scrapy.Request(
    url="https://example.org",
    meta={"playwright": True, "playwright_context": "first"},
)
```

### Creating a context during a crawl

If the context specified in the `playwright_context` meta key does not exist, it will be created.
You can specify keyword arguments to be passed to
[`Browser.new_context`](https://playwright.dev/python/docs/api/class-browser#browser-new-context)
in the `playwright_context_kwargs` meta key:

```python
yield scrapy.Request(
    url="https://example.org",
    meta={
        "playwright": True,
        "playwright_context": "new",
        "playwright_context_kwargs": {
            "java_script_enabled": False,
            "ignore_https_errors": True,
            "proxy": {
                "server": "http://myproxy.com:3128",
                "username": "user",
                "password": "pass",
            },
        },
    },
)
```

Please note that if a context with the specified name already exists,
that context is used and `playwright_context_kwargs` are ignored.

### Closing a context during a crawl

After [receiving the Page object in your callback](#receiving-the-page-object-in-the-callback),
you can access a context though the corresponding [`Page.context`](https://playwright.dev/python/docs/api/class-page#page-context)
attribute, and await [`close`](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-close) on it.

```python
def parse(self, response):
    yield scrapy.Request(
        url="https://example.org",
        callback=self.parse_in_new_context,
        meta={"playwright": True, "playwright_context": "new", "playwright_include_page": True},
    )

async def parse_in_new_context(self, response):
    page = response.meta["playwright_page"]
    title = await page.title()
    await page.context.close()  # close the context
    await page.close()
    return {"title": title}
```


## Proxy support

Proxies are supported at the Browser level by specifying the `proxy` key in
the `PLAYWRIGHT_LAUNCH_OPTIONS` setting:

```python
from scrapy import Spider, Request

class ProxySpider(Spider):
    name = "proxy"
    custom_settings = {
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "proxy": {
                "server": "http://myproxy.com:3128"
                "username": "user",
                "password": "pass",
            },
        }
    }

    def start_requests(self):
        yield Request("http://httpbin.org/get", meta={"playwright": True})

    def parse(self, response):
        print(response.text)
```

You can also set proxies per context with the `PLAYWRIGHT_CONTEXTS` setting:

```python
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "proxy": {
            "server": "http://default-proxy.com:3128",
            "username": "user1",
            "password": "pass1",
        },
    },
    "alternative": {
        "proxy": {
            "server": "http://alternative-proxy.com:3128",
            "username": "user2",
            "password": "pass2",
        },
    },
}
```

Or passing a `proxy` key when [creating a context during a crawl](#creating-a-context-during-a-crawl).

See also the [upstream Playwright section](https://playwright.dev/python/docs/network#http-proxy)
on HTTP Proxies.


## Executing actions on pages

A sorted iterable (`list`, `tuple` or `dict`, for instance) could be passed
in the `playwright_page_methods`
[Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
key to request coroutines to be awaited on the `Page` before returning the final
`Response` to the callback.

This is useful when you need to perform certain actions on a page, like scrolling
down or clicking links, and you want to handle only the final result in your callback.

### `PageMethod` class

#### `scrapy_playwright.page.PageMethod(method: str, *args, **kwargs)`:

Represents a method to be called (and awaited if necessary) on a
`playwright.page.Page` object, such as "click", "screenshot", "evaluate", etc.
`method` is the name of the method, `*args` and `**kwargs`
are passed when calling such method. The return value
will be stored in the `PageMethod.result` attribute.

For instance:
```python
def start_requests(self):
    yield Request(
        url="https://example.org",
        meta={
            "playwright": True,
            "playwright_page_methods": [
                PageMethod("screenshot", path="example.png", fullPage=True),
            ],
        },
    )

def parse(self, response):
    screenshot = response.meta["playwright_page_methods"][0]
    # screenshot.result contains the image's bytes
```

produces the same effect as:
```python
def start_requests(self):
    yield Request(
        url="https://example.org",
        meta={"playwright": True, "playwright_include_page": True},
    )

async def parse(self, response):
    page = response.meta["playwright_page"]
    screenshot = await page.screenshot(path="example.png", full_page=True)
    # screenshot contains the image's bytes
    await page.close()
```


### Supported methods

Please refer to the [upstream docs for the `Page` class](https://playwright.dev/python/docs/api/class-page)
to see available methods.

### Impact on Response objects

Certain `Response` attributes (e.g. `url`, `ip_address`) reflect the state after the last
action performed on a page. If you issue a `PageMethod` with an action that results in
a navigation (e.g. a `click` on a link), the `Response.url` attribute will point to the
new URL, which might be different from the request's URL.


## Handling page events

A dictionary of Page event handlers can be specified in the `playwright_page_event_handlers`
[Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta) key.
Keys are the name of the event to be handled (`dialog`, `download`, etc).
Values can be either callables or strings (in which case a spider method with the name will be looked up).

Example:

```python
from playwright.async_api import Dialog

async def handle_dialog(dialog: Dialog) -> None:
    logging.info(f"Handled dialog with message: {dialog.message}")
    await dialog.dismiss()

class EventSpider(scrapy.Spider):
    name = "event"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta=dict(
                playwright=True,
                playwright_page_event_handlers={
                    "dialog": handle_dialog,
                    "response": "handle_response",
                },
            ),
        )

    async def handle_response(self, response: PlaywrightResponse) -> None:
        logging.info(f"Received response with URL {response.url}")
```

See the [upstream `Page` docs](https://playwright.dev/python/docs/api/class-page) for a list of
the accepted events and the arguments passed to their handlers.

**Note**: keep in mind that, unless they are
[removed later](https://playwright.dev/python/docs/events#addingremoving-event-listener),
these handlers will remain attached to the page and will be called for subsequent
downloads using the same page. This is usually not a problem, since by default
requests are performed in single-use pages.


## Examples

**Click on a link, save the resulting page as PDF**

```python
class ClickAndSavePdfSpider(scrapy.Spider):
    name = "pdf"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta=dict(
                playwright=True,
                playwright_page_methods={
                    "click": PageMethod("click", selector="a"),
                    "pdf": PageMethod("pdf", path="/tmp/file.pdf"),
                },
            ),
        )

    def parse(self, response):
        pdf_bytes = response.meta["playwright_page_methods"]["pdf"].result
        with open("iana.pdf", "wb") as fp:
            fp.write(pdf_bytes)
        yield {"url": response.url}  # response.url is "https://www.iana.org/domains/reserved"
```

**Scroll down on an infinite scroll page, take a screenshot of the full page**

```python
class ScrollSpider(scrapy.Spider):
    name = "scroll"

    def start_requests(self):
        yield scrapy.Request(
            url="http://quotes.toscrape.com/scroll",
            meta=dict(
                playwright=True,
                playwright_include_page=True,
                playwright_page_methods=[
                    PageMethod("wait_for_selector", "div.quote"),
                    PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                    PageMethod("wait_for_selector", "div.quote:nth-child(11)"),  # 10 per page
                ],
            ),
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        await page.screenshot(path="quotes.png", fullPage=True)
        await page.close()
        return {"quote_count": len(response.css("div.quote"))}  # quotes from several pages
```


For more examples, please see the scripts in the [examples](examples) directory.


## Known limitations

* This package does not work natively on Windows. See
  [this comment](https://github.com/scrapy-plugins/scrapy-playwright/issues/7#issuecomment-808824121)
  for more infomation. Additionally, please see
  [this comment](https://github.com/scrapy-plugins/scrapy-playwright/issues/7#issuecomment-817394494)
  for a possible workaround.

* Specifying a proxy via the `proxy` Request meta key is not supported.
  Refer to the [Proxy support](#proxy-support) section for more information.


## Deprecation policy

Deprecated features will be supported for at least six months
following the release that deprecated them. After that, they
may be removed at any time. See the [changelog](changelog.md)
for more information about deprecations and removals.

### Currently deprecated features

* `scrapy_playwright.headers.use_playwright_headers` function

    Deprecated since
    [`v0.0.16`](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.16),
    set `PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None` instead

* `scrapy_playwright.page.PageCoroutine` class

    Deprecated since
    [`v0.0.14`](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.14),
    use `scrapy_playwright.page.PageMethod` instead

* `playwright_page_coroutines` Request meta key

    Deprecated since
    [`v0.0.14`](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.14),
    use `playwright_page_methods` instead
