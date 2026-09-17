.. _memusage:

======================
Memory usage extension
======================

The default Scrapy memory usage extension,
:class:`scrapy.extensions.memusage.MemoryUsage`, does not account for the
memory used by Playwright, because the browser runs as a separate process.
scrapy-playwright provides a replacement that does. It requires the psutil_
package.

.. _psutil: https://pypi.org/project/psutil/

Update the :setting:`EXTENSIONS <scrapy:EXTENSIONS>` setting to disable the
built-in extension and enable this one instead:

.. code-block:: python

    # settings.py
    EXTENSIONS = {
        "scrapy.extensions.memusage.MemoryUsage": None,
        "scrapy_playwright.memusage.ScrapyPlaywrightMemoryUsageExtension": 0,
    }

Refer to the :ref:`upstream docs <scrapy:topics-extensions-ref-memusage>` for
the supported settings.

Like the upstream extension, this one does not work on Windows, because the
standard library :mod:`resource` module is not available there.
