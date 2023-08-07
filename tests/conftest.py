"""
Taken from
https://github.com/pytest-dev/pytest-asyncio/blob/25cf2b399e00a82b69951474eed074ba26cd0c3b/pytest_asyncio/plugin.py

Modify pytest_pycollect_makeitem to make use of the Function API
in pytest>=5.4.0 (pytest.Function.from_parent).

In the context of scrapy-playwright, this allows to unpin the outdated pytest<5.4.0 dependency,
while keeping pytest-asyncio==0.10, as pytest-asyncio>=0.11 currently breaks tests.
"""


import asyncio
import inspect

import pytest


def _is_coroutine(obj):
    """Check to see if an object is really an asyncio coroutine."""
    return asyncio.iscoroutinefunction(obj) or inspect.isgeneratorfunction(obj)


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(collector, name, obj):
    """A pytest hook to collect asyncio coroutines."""
    if collector.funcnamefilter(name) and _is_coroutine(obj):
        item = pytest.Function.from_parent(collector, name=name)
        if "asyncio" in item.keywords:
            return list(collector._genfunctions(name, obj))
    return None
