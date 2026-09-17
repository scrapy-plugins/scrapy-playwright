.. _faq:

==========================
Frequently asked questions
==========================

How to use scrapy-playwright with CrawlSpider?
==============================================

Specify a ``process_request`` method that modifies requests in place in your
:class:`~scrapy.spiders.CrawlSpider` :class:`~scrapy.spiders.Rule` objects:

.. code-block:: python

    def set_playwright_true(request, response):
        request.meta["playwright"] = True
        return request


    class MyCrawlSpider(CrawlSpider):
        rules = (
            Rule(
                link_extractor=LinkExtractor(...),
                callback="parse_item",
                follow=False,
                process_request=set_playwright_true,
            ),
        )


How to download all requests using scrapy-playwright?
=====================================================

Use a middleware to edit the :attr:`Request.meta <scrapy.http.Request.meta>`
attribute of all requests. This saves repetition, and it is the only option
for generic spiders that do not support request customization, such as
:class:`~scrapy.spiders.SitemapSpider`.

Depending on your project and on the interactions with other components, you
might decide to use a :ref:`spider middleware
<scrapy:topics-spider-middleware>`:

.. code-block:: python

    class PlaywrightSpiderMiddleware:
        def process_spider_output(self, response, result, spider):
            for obj in result:
                if isinstance(obj, scrapy.Request):
                    obj.meta.setdefault("playwright", True)
                yield obj

Or a :ref:`downloader middleware <scrapy:topics-downloader-middleware>`:

.. code-block:: python

    class PlaywrightDownloaderMiddleware:
        def process_request(self, request, spider):
            request.meta.setdefault("playwright", True)
            return None


How to increase the allowed memory size for the browser?
========================================================

Messages such as ``JavaScript heap out of memory`` suggest you are falling
into the scope of :gh:`microsoft/playwright#6319`. As a workaround, increase
the amount of memory allowed for the Node.js process through the
``--max-old-space-size`` V8 option, in the ``NODE_OPTIONS`` environment
variable:

.. code-block:: shell

    export NODE_OPTIONS=--max-old-space-size=SIZE  # in megabytes

Sources and further reading:

-   `A comment on #19
    <https://github.com/scrapy-plugins/scrapy-playwright/issues/19#issuecomment-886211045>`__

-   `npm/npm#12238 <https://github.com/npm/npm/issues/12238#issuecomment-367147962>`__

-   `NODE_OPTIONS has landed in 8.x
    <https://medium.com/the-node-js-collection/node-options-has-landed-in-8-x-5fba57af703d>`__

-   `Node.js CLI options
    <https://nodejs.org/api/cli.html#cli_node_options_options>`__

-   `--max-old-space-size
    <https://nodejs.org/api/cli.html#cli_max_old_space_size_size_in_megabytes>`__
