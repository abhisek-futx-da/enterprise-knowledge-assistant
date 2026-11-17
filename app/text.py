import re

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have how i in is it its of on or that the this to was "
    "what when where which who why will with do does did can you your we our".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]
