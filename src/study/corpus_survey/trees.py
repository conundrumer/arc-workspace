"""The arclog and arcdata files of `gen/` as plain trees: a list per list
node, a `str` per symbol, a `Quoted` per string, as `arclog_convert.lint_read`
reads them; and the solvers of `gen/` a section reads."""

from collections.abc import Iterator
from pathlib import Path

from arclog_convert import lint_read, out
from arclog_convert.readback import read_checked


class Quoted(str):
    """A string of the file, its quotes taken off: no symbol."""


type Node = str | list["Node"]


def gen_dir() -> Path:
    """`gen/` under the directory the converter writes."""
    return out() / "gen"


def _plain(node: object) -> Node:
    if isinstance(node, lint_read.L):
        return [_plain(x) for x in node.items]
    if isinstance(node, lint_read.Str):
        return Quoted(node.text[1:-1])
    assert isinstance(node, lint_read.Sym)
    return node.text


def read(path: Path) -> list[Node]:
    """The top-level forms of the file at `path`, a file of a `gen/` directory, read through
    `arclog_convert.readback.read_checked`."""
    return [_plain(x) for x in lint_read.read(read_checked(path))]


def stems(gen: Path) -> list[str]:
    """The stem of each `.arclog` file of `gen`, sorted."""
    return sorted(p.stem for p in gen.glob("*.arclog"))


def arclog(gen: Path, stem: str) -> list[Node]:
    return read(gen / f"{stem}.arclog")


def arcdata(gen: Path, stem: str) -> list[Node]:
    return read(gen / f"{stem}.arcdata")


def is_list(x: object) -> bool:
    return isinstance(x, list)


def is_sym(x: object) -> bool:
    return isinstance(x, str) and not isinstance(x, Quoted)


def head(x: Node) -> str | None:
    """The symbol a list node starts with."""
    return x[0] if isinstance(x, list) and x and is_sym(x[0]) else None  # type: ignore[return-value]


def nodes(x: Node) -> Iterator[list[Node]]:
    """Each list node of `x`, `x` first, in the order of the text."""
    if isinstance(x, list):
        yield x
        for y in x:
            yield from nodes(y)


def symbols(x: Node) -> Iterator[str]:
    """Each symbol of `x`, in the order of the text."""
    if isinstance(x, list):
        for y in x:
            yield from symbols(y)
    elif is_sym(x):
        yield x
