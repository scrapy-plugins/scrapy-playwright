.. _usage:

===========
Basic usage
===========

Set the :reqmeta:`playwright` :attr:`Request.meta <scrapy.http.Request.meta>`
key to download a request using Playwright:

.. code-block:: python

    import scrapy


    class AwesomeSpider(scrapy.Spider):
        name = "awesome"

        async def start(self):
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

The examples throughout this documentation use the ``async start`` spider
method, introduced in Scrapy 2.13. Replace it with ``def start_requests`` if
you are using an older Scrapy version.


User-Agent header
=================

Outgoing requests include the ``User-Agent`` set by Scrapy, either through the
:setting:`USER_AGENT <scrapy:USER_AGENT>` or
:setting:`DEFAULT_REQUEST_HEADERS <scrapy:DEFAULT_REQUEST_HEADERS>` settings or
through the :attr:`Request.headers <scrapy.http.Request.headers>` attribute.
This could make some sites react in unexpected ways, for instance if the user
agent does not match the running browser. To use the ``User-Agent`` that the
browser sends by default, set the Scrapy user agent to ``None``.


Response body and type
======================

The body of a Playwright response is the serialized DOM of the page, as
rendered by the browser. Browsers wrap non-HTML content in HTML tags of their
own: a JSON document is usually displayed inside a ``<pre>`` tag, sometimes
along with viewer-specific markup. Because of that, responses are
:class:`~scrapy.http.HtmlResponse` regardless of the ``Content-Type`` header
reported by the server, and the body of a request to a JSON endpoint cannot be
parsed directly with :meth:`Response.json <scrapy.http.TextResponse.json>` or
:meth:`Response.jmespath <scrapy.http.TextResponse.jmespath>`. Extract the text
node first:

.. code-block:: python

    import json


    def parse(self, response, **kwargs):
        data = json.loads(response.css("pre::text").get())

:reqmeta:`Downloads <playwright_suggested_filename>` keep the bytes and the
type of the downloaded file.
