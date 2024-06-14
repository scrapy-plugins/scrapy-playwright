import platform

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # https://twistedmatrix.com/trac/ticket/9766
    # https://github.com/pytest-dev/pytest-twisted/issues/80

    if (
        config.getoption("reactor", "default") == "asyncio"
        and platform.system() == "Windows"
    ):
        import asyncio

        selector_policy = asyncio.WindowsSelectorEventLoopPolicy()
        asyncio.set_event_loop_policy(selector_policy)


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
