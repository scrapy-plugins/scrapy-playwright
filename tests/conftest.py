import platform

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # https://twistedmatrix.com/trac/ticket/9766
    # https://github.com/pytest-dev/pytest-twisted/issues/80

    import asyncio

    if config.getoption("reactor", "default") == "asyncio" and platform.system() == "Windows":
        selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(selector_policy)

    # Ensure there's a running event loop for the tests
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def pytest_sessionstart(session):  # pylint: disable=unused-argument
    """
    Called after the Session object has been created and before performing
    collection and entering the run test loop.
    """
    from twisted.internet.asyncioreactor import install, AsyncioSelectorReactor
    from twisted.internet.error import ReactorAlreadyInstalledError

    try:
        install()
    except ReactorAlreadyInstalledError as exc:
        from twisted.internet import reactor

        if not isinstance(reactor, AsyncioSelectorReactor):
            raise RuntimeError(f"Wrong reactor installed: {type(reactor)}") from exc
