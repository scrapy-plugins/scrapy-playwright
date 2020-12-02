class PageCoroutine:
    """
    Represents a coroutine to be awaited on a Playwright page,
    such as "click", "screenshot" or "evaluate"
    """

    def __init__(self, method: str, *args, **kwargs) -> None:
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def __str__(self):
        return "<%s for method '%s'>" % (self.__class__.__name__, self.method)

    __repr__ = __str__
