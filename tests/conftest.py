"""
Taken from
https://github.com/pytest-dev/pytest-asyncio/blob/25cf2b399e00a82b69951474eed074ba26cd0c3b/pytest_asyncio/plugin.py

Modify pytest_pycollect_makeitem to make use of the Function API
in pytest>=5.4.0 (pytest.Function.from_parent).

In the context of scrapy-playwright, this allows to unpin the outdated pytest<5.4.0 dependency,
while keeping pytest-asyncio==0.10, as pytest-asyncio>=0.11 currently breaks tests
(likely to be because of https://github.com/pytest-dev/pytest-asyncio/issues/157).
"""


import asyncio
import inspect

import pytest

try:
    from _pytest.python import transfer_markers
except ImportError:  # Pytest 4.1.0 removes the transfer_marker api (#104)

    def transfer_markers(*args, **kwargs):  # noqa
        """Noop when over pytest 4.1.0"""
        pass


def _is_coroutine(obj):
    """Check to see if an object is really an asyncio coroutine."""
    return asyncio.iscoroutinefunction(obj) or inspect.isgeneratorfunction(obj)


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    """A pytest hook to collect asyncio coroutines."""
    if collector.funcnamefilter(name) and _is_coroutine(obj):
        item = pytest.Function.from_parent(collector, name=name)

        # Due to how pytest test collection works, module-level pytestmarks
        # are applied after the collection step. Since this is the collection
        # step, we look ourselves.
        transfer_markers(obj, item.cls, item.module)
        item = pytest.Function.from_parent(collector, name=name)  # To reload keywords.

        if "asyncio" in item.keywords:
            return list(collector._genfunctions(name, obj))
