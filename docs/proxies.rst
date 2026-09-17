.. _proxies:

=============
Proxy support
=============

Proxies are supported at the browser level, through the ``proxy`` key of the
:setting:`PLAYWRIGHT_LAUNCH_OPTIONS` setting:

.. code-block:: python

    from scrapy import Request, Spider


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

        async def start(self):
            yield Request("http://httpbin.org/get", meta={"playwright": True})

        def parse(self, response, **kwargs):
            print(response.text)

They can also be set at the context level, through the
:setting:`PLAYWRIGHT_CONTEXTS` setting or the
:reqmeta:`playwright_context_kwargs` meta key when :ref:`creating contexts
while crawling <create-contexts>`:

.. code-block:: python

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

See also:

-   The `upstream Playwright section on HTTP proxies
    <https://playwright.dev/python/docs/network#http-proxy>`__.

-   `zyte-smartproxy-playwright
    <https://github.com/zytedata/zyte-smartproxy-playwright>`__, which provides
    seamless support for `Zyte Smart Proxy Manager
    <https://www.zyte.com/smart-proxy-manager/>`__ in the Node.js version of
    Playwright.
