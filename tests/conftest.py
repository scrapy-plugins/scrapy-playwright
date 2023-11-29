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
