"""The check of the `<path>` arguments of a script that takes paths from the
root of the tree."""

from pathlib import Path

from transcript_snapshots import Refused

from controlled_markdown import mctx


def refuse_absolute(paths: list[str], script: str) -> None:
    """Refuse the call where a path of `paths` is absolute, citing the
    `--help` text of `scripts/<script>.py`."""
    if bad := [p for p in paths if Path(p).is_absolute()]:
        raise Refused(mctx("{paths} are absolute: give each path from the root of the tree, as "
                           "`uv run python scripts/{script}.py --help` gives").format(
                               paths=", ".join(bad), script=script))
