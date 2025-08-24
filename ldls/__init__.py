from typing import NamedTuple


class Completion(NamedTuple):
    label: str
    detail: str | None = None
    documentation: str | None = None


class Err(NamedTuple):
    line: int
    col: int
    reason: str


class TermInfo(NamedTuple):
    rtype: str | None
    comment: str | None
