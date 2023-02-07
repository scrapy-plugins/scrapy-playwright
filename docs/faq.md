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
