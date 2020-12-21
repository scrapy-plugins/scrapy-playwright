# Playwright integration for Scrapy
[![version](https://img.shields.io/pypi/v/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![pyversions](https://img.shields.io/pypi/pyversions/scrapy-playwright.svg)](https://pypi.python.org/pypi/scrapy-playwright)
[![actions](https://github.com/elacuesta/scrapy-playwright/workflows/Build/badge.svg)](https://github.com/elacuesta/scrapy-playwright/actions)
[![codecov](https://codecov.io/gh/elacuesta/scrapy-playwright/branch/master/graph/badge.svg)](https://codecov.io/gh/elacuesta/scrapy-playwright)


This project provides a Scrapy Download Handler which performs requests using
[Playwright](https://github.com/microsoft/playwright-python). It can be used to handle
pages that require JavaScript. This package does not interfere with regular
Scrapy workflows such as request scheduling or item processing.


## Motivation

After the release of [version 2.0](https://docs.scrapy.org/en/latest/news.html#scrapy-2-0-0-2020-03-03),
which includes partial [coroutine syntax support](https://docs.scrapy.org/en/2.0/topics/coroutines.html)
and experimental [asyncio support](https://docs.scrapy.org/en/2.0/topics/asyncio.html), Scrapy allows
to integrate `asyncio`-based projects such as `Playwright`.


## Requirements

* Python 3.7+
* Scrapy 2.0+
* Playwright 0.7.0+


## Installation

```
$ pip install scrapy-playwright
```


## Configuration

Replace the default `http` and `https` Download Handlers through
[`DOWNLOAD_HANDLERS`](https://docs.scrapy.org/en/latest/topics/settings.html):

```python
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
```

Note that the `ScrapyPlaywrightDownloadHandler` class inherits from the default
`http/https` handler, and it will only use Playwright for requests that are
explicitly marked (see the "Basic usage" section for details).

Also, be sure to [install the `asyncio`-based Twisted reactor](https://docs.scrapy.org/en/latest/topics/asyncio.html#installing-the-asyncio-reactor):

```python
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
```

`scrapy-playwright` accepts the following settings:

* `PLAYWRIGHT_BROWSER_TYPE` (type `str`, default `chromium`)
    The browser type to be launched. Valid values are (`chromium`, `firefox`, `webkit`).
    See the docs for the [`BrowserType` class](https://microsoft.github.io/playwright-python/async_api/index.html#playwright.async_api.BrowserType).

* `PLAYWRIGHT_LAUNCH_OPTIONS` (type `dict`, default `{}`)

    A dictionary with options to be passed when launching the Browser.
    See the docs for [`BrowserType.launch`](https://microsoft.github.io/playwright-python/async_api/index.html#playwright.async_api.BrowserType.launch).

* `PLAYWRIGHT_CONTEXT_ARGS` (type `dict`, default `{}`)

    A dictionary with keyword arguments to be passed when creating the default Browser context.
    See the docs for [`Browser.new_context`](https://microsoft.github.io/playwright-python/async_api/index.html#playwright.async_api.Browser.new_context).

* `PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT` (type `Optional[int]`, default `None`)

    The timeout used when requesting pages by Playwright. If `None` or unset,
    the default value will be used (30000 ms at the time of writing this).
    See the docs for [page.setDefaultNavigationTimeout](https://playwright.dev/#version=v1.6.2&path=docs%2Fapi.md&q=pagesetdefaultnavigationtimeouttimeout).


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


## Page coroutines

A sorted iterable (`list`, `tuple` or `dict`, for instance) could be passed
in the `playwright_page_coroutines`
[Request.meta](https://docs.scrapy.org/en/latest/topics/request-response.html#scrapy.http.Request.meta)
key to request coroutines to be awaited on the `Page` before returning the final
`Response` to the callback.

This is useful when you need to perform certain actions on a page, like scrolling
down or clicking links, and you want everything to count as a single Scrapy
Response, containing the final result.

### Supported actions

* `scrapy_playwright.page.PageCoroutine(method: str, *args, **kwargs)`:

    _Represents a coroutine to be awaited on a `playwright.page.Page` object,
    such as "click", "screenshot", "evaluate", etc.
    `method` should be the name of the coroutine, `*args` and `**kwargs`
    are passed to the function call._

    _The coroutine result will be stored in the `PageCoroutine.result` attribute_

    For instance,
    ```python
    PageCoroutine("screenshot", options={"path": "quotes.png", "fullPage": True})
    ```

    produces the same effect as:
    ```python
    # 'page' is a playwright.async_api.Page object
    await page.screenshot(options={"path": "quotes.png", "fullPage": True})
    ```


### Receiving the Page object in the callback

Specifying a non-False value for the `playwright_include_page` `meta` key for a
request will result in the corresponding `playwright.async_api.Page` object
being available in the `playwright_page` meta key in the request callback.
In order to be able to `await` coroutines on the provided `Page` object,
the callback needs to be defined as a coroutine function (`async def`).

```python
import scrapy
import playwright

class AwesomeSpiderWithPage(scrapy.Spider):
    name = "page"

    def start_requests(self):
        yield scrapy.Request(
            url="https://example.org",
            meta={"playwright": True, "playwright_include_page": True},
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        title = await page.title()  # "Example Domain"
        yield {"title": title}
        await page.close()
```

**Notes:**

* In order to avoid memory issues, it is recommended to manually close the page
  by awaiting the `Page.close` coroutine.
* Any network operations resulting from awaiting a coroutine on a `Page` object
  (`goto`, `goBack`, etc) will be executed directly by Playwright, bypassing the
  Scrapy request workflow (Scheduler, Middlewares, etc).


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
                playwright_page_coroutines={
                    "click": PageCoroutine("click", selector="a"),
                    "pdf": PageCoroutine("pdf", options={"path": "/tmp/file.pdf"}),
                },
            ),
        )

    def parse(self, response):
        pdf_bytes = response.meta["playwright_page_coroutines"]["pdf"].result
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
                playwright_page_coroutines=[
                    PageCoroutine("waitForSelector", "div.quote"),
                    PageCoroutine("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                    PageCoroutine("waitForSelector", "div.quote:nth-child(11)"),  # 10 per page
                ],
            ),
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        await page.screenshot(options={"path": "quotes.png", "fullPage": True})
        yield {"quote_count": len(response.css("div.quote"))}  # quotes from several pages
        await page.close()
```
