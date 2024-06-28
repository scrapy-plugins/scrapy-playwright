# scrapy-playwright: Playwright integration for Scrapy
[![version](https://img.shields.io/pypi/v/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![pyversions](https://img.shields.io/pypi/pyversions/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![Tests](https://github.com/scrapy-plugins/scrapy-playwright/actions/workflows/tests.yml/badge.svg)](https://github.com/scrapy-plugins/scrapy-playwright/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/scrapy-plugins/scrapy-playwright/branch/master/graph/badge.svg)](https://codecov.io/gh/scrapy-plugins/scrapy-playwright)


A [Scrapy](https://github.com/scrapy/scrapy) Download Handler which performs requests using
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

* Python >= 3.8
* Scrapy >= 2.0 (!= 2.4.0)
* Playwright >= 1.15


## Installation

`scrapy-playwright` is available on PyPI and can be installed with `pip`:

```
pip install scrapy-playwright
```

`playwright` is defined as a dependency so it gets installed automatically,
however it might be necessary to install the specific browser(s) that will be
used:

```
playwright install
```

It's also possible to install only a subset of the available browsers:

```
playwright install firefox chromium
```

## Changelog

See the [changelog](docs/changelog.md) document.


## Activation

### Download handler

Replace the default `http` and/or `https` Download Handlers through
[`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html):

```python
# settings.py
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
```

Note that the `ScrapyPlaywrightDownloadHandler` class inherits from the default
`http/https` handler. Unless explicitly marked (see [Basic usage](#basic-usage)),
requests will be processed by the regular Scrapy download handler.


### Twisted reactor

When running on GNU/Linux or macOS you'll need to
[install the `asyncio`-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor):

```python
# settings.py
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

This is not a requirement on Windows (see [Windows support](#windows-support))


## Basic usage

Set the [`playwright`](#playwright) [Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
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

    def parse(self, response, **kwargs):
        # 'response' contains the page as seen by the browser
        return {"url": response.url}
```

### Notes about the User-Agent header

By default, outgoing requests include the `User-Agent` set by Scrapy (either with the
`USER_AGENT` or `DEFAULT_REQUEST_HEADERS` settings or via the `Request.headers` attribute).
This could cause some sites to react in unexpected ways, for instance if the user agent
does not match the running Browser. If you prefer the `User-Agent` sent by
default by the specific browser you're using, set the Scrapy user agent to `None`.


## Windows support

Windows support is possible by running Playwright in a `ProactorEventLoop` in a separate thread.
This is necessary because it's not possible to run Playwright in the same
asyncio event loop as the Scrapy crawler:
* Playwright runs the driver in a subprocess. Source:
  [Playwright repository](https://github.com/microsoft/playwright-python/blob/v1.44.0/playwright/_impl/_transport.py#L120-L130).
* "On Windows, the default event loop `ProactorEventLoop` supports subprocesses,
  whereas `SelectorEventLoop` does not". Source:
  [Python docs](https://docs.python.org/3/library/asyncio-platforms.html#asyncio-windows-subprocess).
* Twisted's `asyncio` reactor requires the `SelectorEventLoop`. Source:
  [Twisted repository](https://github.com/twisted/twisted/blob/twisted-24.3.0/src/twisted/internet/asyncioreactor.py#L31)


## Supported [settings](https://docs.scrapy.org/en/latest/topics/settings.html)

### `PLAYWRIGHT_BROWSER_TYPE`
Type `str`, default `"chromium"`.

The browser type to be launched, e.g. `chromium`, `firefox`, `webkit`.

```python
PLAYWRIGHT_BROWSER_TYPE = "firefox"
```

### `PLAYWRIGHT_LAUNCH_OPTIONS`
Type `dict`, default `{}`

A dictionary with options to be passed as keyword arguments when launching the
Browser. See the docs for
[`BrowserType.launch`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch)
for a list of supported keyword arguments.

```python
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": False,
    "timeout": 20 * 1000,  # 20 seconds
}
```

### `PLAYWRIGHT_CDP_URL`
Type `Optional[str]`, default `None`

The endpoint of a remote Chromium browser to connect using the
[Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/),
via [`BrowserType.connect_over_cdp`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp).
If this setting is used:
* all non-persistent contexts will be created on the connected remote browser
* the `PLAYWRIGHT_LAUNCH_OPTIONS` setting is ignored
* the `PLAYWRIGHT_BROWSER_TYPE` setting must not be set to a value different than "chromium"

```python
PLAYWRIGHT_CDP_URL = "http://localhost:9222"
```

### `PLAYWRIGHT_CDP_KWARGS`
Type `dict[str, Any]`, default `{}`

Additional keyword arguments to be passed to
[`BrowserType.connect_over_cdp`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
when using `PLAYWRIGHT_CDP_URL`. The `endpoint_url` key is always ignored,
`PLAYWRIGHT_CDP_URL` is used instead.

```python
PLAYWRIGHT_CDP_KWARGS = {
    "slow_mo": 1000,
    "timeout": 10 * 1000
}
```


### `PLAYWRIGHT_CONTEXTS`
Type `dict[str, dict]`, default `{}`

A dictionary which defines Browser contexts to be created on startup.
It should be a mapping of (name, keyword arguments).

```python
PLAYWRIGHT_CONTEXTS = {
    "foobar": {
        "context_arg1": "value",
        "context_arg2": "value",
    },
    "default": {
        "context_arg1": "value",
        "context_arg2": "value",
    },
    "persistent": {
        "user_data_dir": "/path/to/dir",  # will be a persistent context
        "context_arg1": "value",
    },
}
```

See the section on [browser contexts](#browser-contexts) for more information.
See also the docs for [`Browser.new_context`](https://playwright.dev/python/docs/api/class-browser#browser-new-context).

### `PLAYWRIGHT_MAX_CONTEXTS`
Type `Optional[int]`, default `None`

Maximum amount of allowed concurrent Playwright contexts. If unset or `None`,
no limit is enforced. See the [Maximum concurrent context count](#maximum-concurrent-context-count)
section for more information.

```python
PLAYWRIGHT_MAX_CONTEXTS = 8
```

### `PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT`
Type `Optional[float]`, default `None`

Timeout to be used when requesting pages by Playwright, in milliseconds. If
`None` or unset, the default value will be used (30000 ms at the time of writing).
See the docs for [BrowserContext.set_default_navigation_timeout](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-set-default-navigation-timeout).

```python
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 10 * 1000  # 10 seconds
```

### `PLAYWRIGHT_PROCESS_REQUEST_HEADERS`
Type `Optional[Union[Callable, str]]`, default `scrapy_playwright.headers.use_scrapy_headers`

A function (or the path to a function) that processes headers for a given request
and returns a dictionary with the headers to be used (note that, depending on the browser,
additional default headers could be sent as well). Coroutine functions (`async def`) are
supported.

This will be called at least once for each Scrapy request (receiving said request and the
corresponding Playwright request), but it could be called additional times if the given
resource generates more requests (e.g. to retrieve assets like images or scripts).

The function must return a `dict` object, and receives the following positional arguments:

```python
- browser_type: str
- playwright_request: playwright.async_api.Request
- scrapy_headers: scrapy.http.headers.Headers
```

The default function (`scrapy_playwright.headers.use_scrapy_headers`) tries to
emulate Scrapy's behaviour for navigation requests, i.e. overriding headers
with their values from the Scrapy request. For non-navigation requests (e.g.
images, stylesheets, scripts, etc), only the `User-Agent` header is overriden,
for consistency.

Setting `PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None` will give complete control to
Playwright, i.e. headers from Scrapy requests will be ignored and only headers
set by Playwright will be sent. Keep in mind that in this case, headers passed
via the `Request.headers` attribute or set by Scrapy components are ignored
(including cookies set via the `Request.cookies` attribute).

```python
def custom_headers(
    browser_type: str,
    playwright_request: playwright.async_api.Request,
    scrapy_headers: scrapy.http.headers.Headers,
) -> dict:
    if browser_type == "firefox":
        return {"User-Agent": "foo"}
    return {"User-Agent": "bar"}

PLAYWRIGHT_PROCESS_REQUEST_HEADERS = custom_headers
```

### `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT`
Type `int`, defaults to the value of Scrapy's `CONCURRENT_REQUESTS` setting

Maximum amount of allowed concurrent Playwright pages for each context.
See the [notes about leaving unclosed pages](#receiving-page-objects-in-callbacks).

```python
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 4
```

### `PLAYWRIGHT_ABORT_REQUEST`
Type `Optional[Union[Callable, str]]`, default `None`

A predicate function (or the path to a function) that receives a
[`playwright.async_api.Request`](https://playwright.dev/python/docs/api/class-request)
object and must return `True` if the request should be aborted, `False` otherwise.
Coroutine functions (`async def`) are supported.

Note that all requests will appear in the DEBUG level logs, however there will
be no corresponding response log lines for aborted requests. Aborted requests
are counted in the `playwright/request_count/aborted` job stats item.

```python
def should_abort_request(request):
    return (
        request.resource_type == "image"
        or ".jpg" in request.url
    )

PLAYWRIGHT_ABORT_REQUEST = should_abort_request
```

### General note about settings
For settings that accept object paths as strings, passing callable objects is
only supported when using Scrapy>=2.4. With prior versions, only strings are
supported.


## Supported [`Request.meta`](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta) keys

### `playwright`
Type `bool`, default `False`

If set to a value that evaluates to `True` the request will be processed by Playwright.

```python
return scrapy.Request("https://example.org", meta={"playwright": True})
```

### `playwright_context`
Type `str`, default `"default"`

Name of the context to be used to download the request.
See the section on [browser contexts](#browser-contexts) for more information.

```python
return scrapy.Request(
    url="https://example.org",
    meta={
        "playwright": True,
        "playwright_context": "awesome_context",
    },
)
```

### `playwright_context_kwargs`
Type `dict`, default `{}`

A dictionary with keyword arguments to be used when creating a new context, if a context
with the name specified in the `playwright_context` meta key does not exist already.
See the section on [browser contexts](#browser-contexts) for more information.

```python
return scrapy.Request(
    url="https://example.org",
    meta={
        "playwright": True,
        "playwright_context": "awesome_context",
        "playwright_context_kwargs": {
            "ignore_https_errors": True,
        },
    },
)
```

### `playwright_include_page`
Type `bool`, default `False`

If `True`, the [Playwright page](https://playwright.dev/python/docs/api/class-page)
that was used to download the request will be available in the callback at
`response.meta['playwright_page']`. If `False` (or unset) the page will be
closed immediately after processing the request.

**Important!**

This meta key is entirely optional, it's NOT necessary for the page to load or for any
asynchronous operation to be performed (specifically, it's NOT necessary for `PageMethod`
objects to be applied). Use it only if you need access to the Page object in the callback
that handles the response.

For more information and important notes see
[Receiving Page objects in callbacks](#receiving-page-objects-in-callbacks).

```python
return scrapy.Request(
    url="https://example.org",
    meta={"playwright": True, "playwright_include_page": True},
)
```

### `playwright_page_event_handlers`
Type `Dict[Str, Callable]`, default `{}`

A dictionary of handlers to be attached to page events.
See [Handling page events](#handling-page-events).

### `playwright_page_init_callback`
Type `Optional[Union[Callable, str]]`, default `None`

A coroutine function (`async def`) to be invoked for newly created pages.
Called after attaching page event handlers & setting up internal route
handling, before making any request. It receives the Playwright page and the
Scrapy request as positional arguments. Useful for initialization code.
Ignored if the page for the request already exists (e.g. by passing
`playwright_page`).

```python
async def init_page(page, request):
    await page.add_init_script(path="./custom_script.js")

class AwesomeSpider(scrapy.Spider):
    def start_requests(self):
        yield scrapy.Request(
            url="https://httpbin.org/headers",
            meta={
                "playwright": True,
                "playwright_page_init_callback": init_page,
            },
        )
```

**Important!**

`scrapy-playwright` uses `Page.route` & `Page.unroute` internally, avoid using
these methods unless you know exactly what you're doing.

### `playwright_page_methods`
Type `Iterable[PageMethod]`, default `()`

An iterable of [`scrapy_playwright.page.PageMethod`](#pagemethod-class)
objects to indicate actions to be performed on the page before returning the
final response. See [Executing actions on pages](#executing-actions-on-pages).

### `playwright_page`
Type `Optional[playwright.async_api.Page]`, default `None`

A [Playwright page](https://playwright.dev/python/docs/api/class-page) to be used to
download the request. If unspecified, a new page is created for each request.
This key could be used in conjunction with `playwright_include_page` to make a chain of
requests using the same page. For instance:

```python
def start_requests(self):
    yield scrapy.Request(
        url="https://httpbin.org/get",
        meta={"playwright": True, "playwright_include_page": True},
    )

def parse(self, response, **kwargs):
    page = response.meta["playwright_page"]
    yield scrapy.Request(
        url="https://httpbin.org/headers",
        callback=self.parse_headers,
        meta={"playwright": True, "playwright_page": page},
    )
```

### `playwright_page_goto_kwargs`
Type `dict`, default `{}`

A dictionary with keyword arguments to be passed to the page's
[`goto` method](https://playwright.dev/python/docs/api/class-page#page-goto)
when navigating to an URL. The `url` key is ignored if present, the request
URL is used instead.

```python
return scrapy.Request(
    url="https://example.org",
    meta={
        "playwright": True,
        "playwright_page_goto_kwargs": {
            "wait_until": "networkidle",
        },
    },
)
```

### `playwright_security_details`
Type `Optional[dict]`, read only

A dictionary with [security information](https://playwright.dev/python/docs/api/class-response#response-security-details)
about the give response. Only available for HTTPS requests. Could be accessed
in the callback via `response.meta['playwright_security_details']`

```python
def parse(self, response, **kwargs):
    print(response.meta["playwright_security_details"])
    # {'issuer': 'DigiCert TLS RSA SHA256 2020 CA1', 'protocol': 'TLS 1.3', 'subjectName': 'www.example.org', 'validFrom': 1647216000, 'validTo': 1678838399}
```


## Receiving Page objects in callbacks

Specifying a value that evaluates to `True` in the
[`playwright_include_page`](#playwright_include_page) meta key for a
request will result in the corresponding `playwright.async_api.Page` object
being available in the `playwright_page` meta key in the request callback.
In order to be able to `await` coroutines on the provided `Page` object,
the callback needs to be defined as a coroutine function (`async def`).

**Caution**

Use this carefully, and only if you really need to do things with the Page
object in the callback. If pages are not properly closed after they are no longer
necessary the spider job could get stuck because of the limit set by the
`PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` setting.

```python
import scrapy

class AwesomeSpiderWithPage(scrapy.Spider):
    name = "page_spider"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            callback=self.parse_first,
            meta={"playwright": True, "playwright_include_page": True},
            errback=self.errback_close_page,
        )

    def parse_first(self, response):
        page = response.meta["playwright_page"]
        return scrapy.Request(
            url="https://example.com",
            callback=self.parse_second,
            meta={"playwright": True, "playwright_include_page": True, "playwright_page": page},
            errback=self.errback_close_page,
        )

    async def parse_second(self, response):
        page = response.meta["playwright_page"]
        title = await page.title()  # "Example Domain"
        await page.close()
        return {"title": title}

    async def errback_close_page(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()
```

**Notes:**

* When passing `playwright_include_page=True`, make sure pages are always closed
  when they are no longer used. It's recommended to set a Request errback to make
  sure pages are closed even if a request fails (if `playwright_include_page=False`
  pages are automatically closed upon encountering an exception).
  This is important, as open pages count towards the limit set by
  `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` and crawls could freeze if the limit is reached
  and pages remain open indefinitely.
* Defining callbacks as `async def` is only necessary if you need to `await` things,
  it's NOT necessary if you just need to pass over the Page object from one callback
  to another (see the example above).
* Any network operations resulting from awaiting a coroutine on a Page object
  (`goto`, `go_back`, etc) will be executed directly by Playwright, bypassing the
  Scrapy request workflow (Scheduler, Middlewares, etc).


## Browser contexts

Multiple [browser contexts](https://playwright.dev/python/docs/browser-contexts)
to be launched at startup can be defined via the
[`PLAYWRIGHT_CONTEXTS`](#playwright_contexts) setting.

### Choosing a specific context for a request

Pass the name of the desired context in the `playwright_context` meta key:

```python
yield scrapy.Request(
    url="https://example.org",
    meta={"playwright": True, "playwright_context": "first"},
)
```

### Default context

If a request does not explicitly indicate a context via the `playwright_context`
meta key, it falls back to using a general context called `default`. This `default`
context can also be customized on startup via the `PLAYWRIGHT_CONTEXTS` setting.

### Persistent contexts

Pass a value for the `user_data_dir` keyword argument to launch a context as
persistent. See also [`BrowserType.launch_persistent_context`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).

Note that persistent contexts are launched independently from the main browser
instance, hence keyword arguments passed in the
[`PLAYWRIGHT_LAUNCH_OPTIONS`](#playwright_launch_options)
setting do not apply.

### Creating contexts while crawling

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

### Closing contexts while crawling

After [receiving the Page object in your callback](#receiving-page-objects-in-callbacks),
you can access a context though the corresponding [`Page.context`](https://playwright.dev/python/docs/api/class-page#page-context)
attribute, and await [`close`](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-close) on it.

```python
def parse(self, response, **kwargs):
    yield scrapy.Request(
        url="https://example.org",
        callback=self.parse_in_new_context,
        errback=self.close_context_on_error,
        meta={
            "playwright": True,
            "playwright_context": "awesome_context",
            "playwright_include_page": True,
        },
    )

async def parse_in_new_context(self, response):
    page = response.meta["playwright_page"]
    title = await page.title()
    await page.close()
    await page.context.close()
    return {"title": title}

async def close_context_on_error(self, failure):
    page = failure.request.meta["playwright_page"]
    await page.close()
    await page.context.close()
```

### Avoid race conditions & memory leaks when closing contexts
Make sure to close the page before closing the context. See
[this comment](https://github.com/scrapy-plugins/scrapy-playwright/issues/191#issuecomment-1548097114)
in [#191](https://github.com/scrapy-plugins/scrapy-playwright/issues/191)
for more information.

### Maximum concurrent context count

Specify a value for the `PLAYWRIGHT_MAX_CONTEXTS` setting to limit the amount
of concurent contexts. Use with caution: it's possible to block the whole crawl
if contexts are not closed after they are no longer used (refer to
[this section](#closing-contexts-while-crawling) to dinamically close contexts).
Make sure to define an errback to still close contexts even if there are errors.


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
                "server": "http://myproxy.com:3128",
                "username": "user",
                "password": "pass",
            },
        }
    }

    def start_requests(self):
        yield Request("http://httpbin.org/get", meta={"playwright": True})

    def parse(self, response, **kwargs):
        print(response.text)
```

Proxies can also be set at the context level with the `PLAYWRIGHT_CONTEXTS` setting:

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

Or passing a `proxy` key when [creating contexts while crawling](#creating-contexts-while-crawling).

See also:
* [`zyte-smartproxy-playwright`](https://github.com/zytedata/zyte-smartproxy-playwright):
  seamless support for [Zyte Smart Proxy Manager](https://www.zyte.com/smart-proxy-manager/)
  in the Node.js version of Playwright.
* the [upstream Playwright for Python section](https://playwright.dev/python/docs/network#http-proxy)
  on HTTP Proxies.


## Executing actions on pages

A sorted iterable (e.g. `list`, `tuple`, `dict`) of `PageMethod` objects
could be passed in the `playwright_page_methods`
[Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
key to request methods to be invoked on the `Page` object before returning the final
`Response` to the callback.

This is useful when you need to perform certain actions on a page (like scrolling
down or clicking links) and you want to handle only the final result in your callback.

### `PageMethod` class

#### `scrapy_playwright.page.PageMethod(method: str, *args, **kwargs)`:

Represents a method to be called (and awaited if necessary) on a
`playwright.page.Page` object (e.g. "click", "screenshot", "evaluate", etc).
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
                PageMethod("screenshot", path="example.png", full_page=True),
            ],
        },
    )

def parse(self, response, **kwargs):
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

async def parse(self, response, **kwargs):
    page = response.meta["playwright_page"]
    screenshot = await page.screenshot(path="example.png", full_page=True)
    # screenshot contains the image's bytes
    await page.close()
```


### Supported methods

Refer to the [upstream docs for the `Page` class](https://playwright.dev/python/docs/api/class-page)
to see available methods.

### Impact on Response objects

Certain `Response` attributes (e.g. `url`, `ip_address`) reflect the state after the last
action performed on a page. If you issue a `PageMethod` with an action that results in
a navigation (e.g. a `click` on a link), the `Response.url` attribute will point to the
new URL, which might be different from the request's URL.


## Handling page events

A dictionary of Page event handlers can be specified in the `playwright_page_event_handlers`
[Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta) key.
Keys are the name of the event to be handled (e.g. `dialog`, `download`, etc).
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
            meta={
                "playwright": True,
                "playwright_page_event_handlers": {
                    "dialog": handle_dialog,
                    "response": "handle_response",
                },
            },
        )

    async def handle_response(self, response: PlaywrightResponse) -> None:
        logging.info(f"Received response with URL {response.url}")
```

See the [upstream `Page` docs](https://playwright.dev/python/docs/api/class-page)
for a list of the accepted events and the arguments passed to their handlers.

### Notes about page event handlers

* Event handlers will remain attached to the page and will be called for
  subsequent downloads using the same page unless they are
  [removed later](https://playwright.dev/python/docs/events#addingremoving-event-listener).
  This is usually not a problem, since by default requests are performed in
  single-use pages.
* Event handlers will process Playwright objects, not Scrapy ones. For example,
  for each Scrapy request/response there will be a matching Playwright
  request/response, but not the other way: background requests/responses to get
  images, scripts, stylesheets, etc are not seen by Scrapy.


## Memory usage extension

The default Scrapy memory usage extension
(`scrapy.extensions.memusage.MemoryUsage`) does not include the memory used by
Playwright because the browser is launched as a separate process. The
scrapy-playwright package provides a replacement extension which also considers
the memory used by Playwright. This extension needs the
[`psutil`](https://pypi.org/project/psutil/) package to work.

Update the [EXTENSIONS](https://docs.scrapy.org/en/latest/topics/settings.html#std-setting-EXTENSIONS)
setting to disable the built-in Scrapy extension and replace it with the one
from the scrapy-playwright package:

```python
# settings.py
EXTENSIONS = {
    "scrapy.extensions.memusage.MemoryUsage": None,
    "scrapy_playwright.memusage.ScrapyPlaywrightMemoryUsageExtension": 0,
}
```

Refer to the
[upstream docs](https://docs.scrapy.org/en/latest/topics/extensions.html#module-scrapy.extensions.memusage)
for more information about supported settings.

### Windows support

Just like the [upstream Scrapy extension](https://docs.scrapy.org/en/latest/topics/extensions.html#module-scrapy.extensions.memusage), this custom memory extension does not work
on Windows. This is because the stdlib [`resource`](https://docs.python.org/3/library/resource.html)
module is not available.


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

    def parse(self, response, **kwargs):
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

    async def parse(self, response, **kwargs):
        page = response.meta["playwright_page"]
        await page.screenshot(path="quotes.png", full_page=True)
        await page.close()
        return {"quote_count": len(response.css("div.quote"))}  # quotes from several pages
```


See the [examples](examples) directory for more.


## Known issues

### No per-request proxy support
Specifying a proxy via the `proxy` Request meta key is not supported.
Refer to the [Proxy support](#proxy-support) section for more information.

### Unsopported signals
The `headers_received` and `bytes_received` signals are not fired by the
scrapy-playwright download handler.


## Reporting issues

Before opening an issue please make sure the unexpected behavior can only be
observed by using this package and not with standalone Playwright. To do this,
translate your spider code to a reasonably close Playwright script: if the
issue also occurs this way, you should instead report it
[upstream](https://github.com/microsoft/playwright-python).
For instance:

```python
import scrapy

class ExampleSpider(scrapy.Spider):
    name = "example"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta=dict(
                playwright=True,
                playwright_page_methods=[
                    PageMethod("screenshot", path="example.png", full_page=True),
                ],
            ),
        )
```

translates roughly to:

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.org")
        await page.screenshot(path="example.png", full_page=True)
        await browser.close()

asyncio.run(main())
```

### Software versions

Be sure to include which versions of Scrapy, Playwright and scrapy-playwright you are using:

```
$ playwright --version
Version 1.44.0
```

```
$ python -c "import scrapy_playwright; print(scrapy_playwright.__version__)"
0.0.34
```

```
$ scrapy version -v
Scrapy       : 2.11.1
lxml         : 5.1.0.0
libxml2      : 2.12.3
cssselect    : 1.2.0
parsel       : 1.8.1
w3lib        : 2.1.2
Twisted      : 23.10.0
Python       : 3.10.12 (main, Nov 20 2023, 15:14:05) [GCC 11.4.0]
pyOpenSSL    : 24.0.0 (OpenSSL 3.2.1 30 Jan 2024)
cryptography : 42.0.5
Platform     : Linux-6.5.0-35-generic-x86_64-with-glibc2.35
```

### Reproducible code example

When opening an issue please include a
[Minimal, Reproducible Example](https://stackoverflow.com/help/minimal-reproducible-example)
that shows the reported behavior. In addition, please make the code as self-contained as possible
so an active Scrapy project is not required and the spider can be executed directly from a file with
[`scrapy runspider`](https://docs.scrapy.org/en/latest/topics/commands.html#std-command-runspider).
This usually means including the relevant settings in the spider's
[`custom_settings`](https://docs.scrapy.org/en/latest/topics/settings.html#settings-per-spider)
attribute:

```python
import scrapy

class ExampleSpider(scrapy.Spider):
    name = "example"
    custom_settings = {
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta={"playwright": True},
        )
```

#### Minimal code
Please make the effort to reduce the code to the minimum that still displays the issue.
It is very rare that a complete project (including middlewares, pipelines, item processing, etc)
is really needed to reproduce an issue. Reports that do not show an actual debugging attempt
will not be considered.

### Logs and stats

Logs for spider jobs displaying the issue in detail are extremely useful
for understanding possible bugs. Include lines before and after the problem,
not just isolated tracebacks. Job stats displayed at the end of the job
are also important.


## Frequently Asked Questions

See the [FAQ](docs/faq.md) document.


## Deprecation policy

Deprecated features will be supported for at least six months
following the release that deprecated them. After that, they
may be removed at any time. See the [changelog](docs/changelog.md)
for more information about deprecations and removals.
