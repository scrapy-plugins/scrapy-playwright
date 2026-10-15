.. _contexts:

================
Browser contexts
================

Multiple `browser contexts
<https://playwright.dev/python/docs/browser-contexts>`__ to be launched at
startup can be defined through the :setting:`PLAYWRIGHT_CONTEXTS` setting.


Choosing a specific context for a request
=========================================

Pass the name of the desired context in the :reqmeta:`playwright_context` meta
key:

.. code-block:: python

    yield scrapy.Request(
        url="https://example.org",
        meta={"playwright": True, "playwright_context": "first"},
    )

A request that does not indicate a context falls back to a general context
called ``default``, which can also be customized on startup through the
:setting:`PLAYWRIGHT_CONTEXTS` setting.


.. _persistent-contexts:

Persistent contexts
===================

Pass a value for the ``user_data_dir`` keyword argument to launch a context as
persistent. See also `BrowserType.launch_persistent_context
<https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context>`__.

Persistent contexts are launched independently from the main browser instance,
so keyword arguments passed in the :setting:`PLAYWRIGHT_LAUNCH_OPTIONS`
setting do not apply to them.

.. important:: When ``ScrapyPlaywrightDownloadHandler`` is registered for both
    the ``http`` and the ``https`` scheme, Scrapy creates one independent
    handler instance per scheme. Both instances read the same
    :setting:`PLAYWRIGHT_CONTEXTS` setting and try to open the same
    ``user_data_dir``, which fails because the browser only allows one process
    per profile directory.

    To avoid that, either make every ``user_data_dir`` value unique across
    handler instances, e.g. by including a random suffix:

    .. code-block:: python

        import uuid

        PLAYWRIGHT_CONTEXTS = {
            "persistent": {
                "user_data_dir": f"/path/to/dir-{uuid.uuid4()}",
                "context_arg1": "value",
            },
        }

    Or register the handler for a single scheme, typically ``https``:

    .. code-block:: python

        DOWNLOAD_HANDLERS = {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        }


.. _create-contexts:

Creating contexts while crawling
================================

If the context specified in the :reqmeta:`playwright_context` meta key does not
exist, it is created. Keyword arguments for `Browser.new_context
<https://playwright.dev/python/docs/api/class-browser#browser-new-context>`__
can be specified in the :reqmeta:`playwright_context_kwargs` meta key:

.. code-block:: python

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

If a context with the specified name already exists, that context is used and
:reqmeta:`playwright_context_kwargs` is ignored.


.. _close-contexts:

Closing contexts while crawling
===============================

After :ref:`receiving the page object in your callback <page-objects>`, you can
access its context through the `Page.context
<https://playwright.dev/python/docs/api/class-page#page-context>`__ attribute,
and await `close
<https://playwright.dev/python/docs/api/class-browsercontext#browser-context-close>`__
on it. Close the page before closing the context, to avoid race conditions and
memory leaks (see :gh:`191`).

.. code-block:: python

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


.. _max-contexts:

Maximum concurrent context count
================================

The :setting:`PLAYWRIGHT_MAX_CONTEXTS` setting limits the amount of concurrent
contexts. Use it with caution: the whole crawl blocks if contexts are not
:ref:`closed <close-contexts>` after they are no longer used. Define an errback
to close contexts even if there are errors.
