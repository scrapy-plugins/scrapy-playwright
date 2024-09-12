from typing import Any, Callable


__all__ = ["PageMethod"]


class PageMethod:
    """
    Represents a method to be called (and awaited if necessary) on a
    Playwright page, such as "click", "screenshot", "evaluate", etc.
    """

    def __init__(self, method: str | Callable, *args, **kwargs) -> None:
        self.method: str | Callable = method
        self.args: tuple = args
        self.kwargs: dict = kwargs
        self.result: Any = None

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} for method '{self.method}'>"

    __repr__ = __str__
