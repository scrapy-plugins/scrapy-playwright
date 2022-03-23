import warnings

from scrapy.exceptions import ScrapyDeprecationWarning

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


class PageCoroutine(PageMethod):
    def __init__(self, method: str, *args, **kwargs) -> None:
        warnings.warn(
            f"The {_qualname(self.__class__)} class is deprecated,"
            f" please use {_qualname(PageMethod)} instead.",
            category=ScrapyDeprecationWarning,
            stacklevel=2,
        )
        super().__init__(method, *args, **kwargs)


def _qualname(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"
