# Frequently Asked Questions


## How to use scrapy-playwright with the [CrawlSpider](https://docs.scrapy.org/en/latest/topics/spiders.html#crawlspider)?

By specifying a `process_request` method that modifies requests in-place in your
[crawling rules](https://docs.scrapy.org/en/latest/topics/spiders.html#scrapy.spiders.Rule).
For instance:

```python
def set_playwright_true(request, response):
    request.meta["playwright"] = True
    return request

class MyCrawlSpider(CrawlSpider):
    ...
    rules = (
        Rule(
            link_extractor=LinkExtractor(...),
            callback="parse_item",
            follow=False,
            process_request=set_playwright_true,
        ),
    )
```


## How to download all requests using scrapy-playwright?

If you want all requests to be processed by Playwright and don't want to repeat
yourself, or you're using a generic spider that doesn't support request
customization (e.g. `scrapy.spiders.SitemapSpider`), you can use a middleware
to edit the `meta` attribute for all requests.

Depending on your project and the interactions with other components, you might
decide to use a
[spider middleware](https://docs.scrapy.org/en/latest/topics/spider-middleware.html)
or a
[downloader middleware](https://docs.scrapy.org/en/latest/topics/downloader-middleware.html).

Spider middleware example:

```python
class PlaywrightSpiderMiddleware:
    def process_spider_output(self, response, result, spider):
        for obj in result:
            if isinstance(obj, scrapy.Request):
                obj.meta.setdefault("playwright", True)
            yield obj
```

Downloader middleware example:

```python
class PlaywrightDownloaderMiddleware:
    def process_request(self, request, spider):
        request.meta.setdefault("playwright", True)
        return None
```


## How to increase the allowed memory size for the browser?

If you're seeing messages such as `JavaScript heap out of memory`, there's a
chance you're falling into the scope of
https://github.com/microsoft/playwright/issues/6319. As a workaround, it's
possible to increase the amount of memory allowed for the Node.js process by
specifying a value for the the `--max-old-space-size` V8 option in the
`NODE_OPTIONS` environment variable, e.g.:

```
$ export NODE_OPTIONS=--max-old-space-size=SIZE  # in megabytes
```

Sources & further reading:
* https://github.com/scrapy-plugins/scrapy-playwright/issues/19#issuecomment-886211045
* https://github.com/npm/npm/issues/12238#issuecomment-367147962
* https://medium.com/the-node-js-collection/node-options-has-landed-in-8-x-5fba57af703d
* https://nodejs.org/dist/latest-v8.x/docs/api/cli.html#cli_node_options_options
* https://nodejs.org/api/cli.html#cli_max_old_space_size_size_in_megabytes
