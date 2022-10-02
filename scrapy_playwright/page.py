__all__ = ["PageMethod"]


class PageMethod:
    """
    Represents a method to be called (and awaited if necessary) on a
    Playwright page, such as "click", "screenshot", "evaluate", etc.
    """

    def __init__(self, method: str, *args, **kwargs) -> None:
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def __str__(self):
        return f"<{self.__class__.__name__} for method '{self.method}'>"

    __repr__ = __str__
