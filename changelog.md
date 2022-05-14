# scrapy-playwright changelog


### [v0.0.16](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.16) (2022-NN-NN)

* Use new headers API introduced in Playwright 1.15 (bump required Playwright version)
* Deprecate `scrapy_playwright.headers.use_playwright_headers`, set `PLAYWRIGHT_PROCESS_REQUEST_HEADERS=None` instead


### [v0.0.15](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.15) (2022-05-08)

* Remove deprecated `PLAYWRIGHT_CONTEXT_ARGS` setting
* Warn on failed requests
* `PLAYWRIGHT_ABORT_REQUEST` setting: accept coroutine functions
* `PLAYWRIGHT_PROCESS_REQUEST_HEADERS` setting: accept sync functions to process headers
* Set `playwright_page` request meta key early


### [v0.0.14](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.14) (2022-03-26)

* Renamed `PageCoroutine` to `PageMethod` (`PageCoroutine` is now deprecated)


### [v0.0.13](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.13) (2022-03-24)

* PageCoroutine checks
* Fix encoding detection
* Ability to abort requests via setting


### [v0.0.12](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.12) (2022-03-15)

* Avoid exceptions during cleanup when the browser could not start
* Warn when non PageCoroutine objects are passed to Request.meta.playwright_page_coroutines


### [v0.0.11](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.11) (2022-03-12)

* Set the maximum amount of pages per context
* Response.ip_address attribute
* Response security details


### [v0.0.10](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.10) (2022-03-02)

* Fix response encoding detection


### [v0.0.9](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.9) (2022-01-27)

* Ability to process request headers


### [v0.0.8](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.8) (2022-01-13)

* Fix PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT setting (allow zero value)


### [v0.0.7](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.7) (2021-10-20)

* Log all requests/responses (debug level)


### [v0.0.6](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.6) (2021-10-19)

* Page event handlers
* Python 3.10 support
* Doc fixes
* Override User-Agent header


### [v0.0.5](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.5) (2021-08-20)

* Improve garbage collection by removing unnecessary reference

### [v0.0.4](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.4) (2021-07-16)

* Add support for multiple browser contexts ([#13](https://github.com/scrapy-plugins/scrapy-playwright/pull/13))
* Deprecate `PLAYWRIGHT_CONTEXT_ARGS` setting in favor of `PLAYWRIGHT_CONTEXTS`


### [v0.0.3](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.3) (2021-02-22)

* Snake case (requires playwright-python >= [v1.8.0a1](https://github.com/microsoft/playwright-python/releases/tag/v1.8.0a1))


### [v0.0.2](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.2) (2021-01-13)

* `PLAYWRIGHT_CONTEXT_ARGS` setting (ability to pass keyword arguments to the browser context)

### [v0.0.1](https://github.com/scrapy-plugins/scrapy-playwright/releases/tag/v0.0.1) (2020-12-18)

Initial public release.
