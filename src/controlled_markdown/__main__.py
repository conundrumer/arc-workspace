"""Check, format, and render Controlled Markdown documents.

    uv run python -m controlled_markdown check [paths...]   # report what is off
    uv run python -m controlled_markdown fmt [paths...]     # rewrite in canonical form
    uv run python -m controlled_markdown render <path> [paths...]

`check` reports each file that fails to parse or is not in canonical form, and
exits 1 when any does. `fmt` rewrites each file in canonical form and prints
the ones it changed. With no path, both read the set under
`[tool.controlled_markdown]` in `pyproject.toml`, so the command that guards the
documents is one word wherever it is written. `render` prints the first path as
ordinary Markdown, with its includes resolved from the files they name, and it
takes its paths as given. A path that names a directory stands for every `.md`
file under it. A name in a message is relative to the current directory.
"""

import sys
import tomllib
from pathlib import Path

from . import (
    NestedMarkdownError,
    Registry,
    check_blocks,
    check_links,
    check_text_links,
    parse,
    render,
    write,
)


def _table(start: Path | None = None) -> tuple[Path, dict]:
    """The `[tool.controlled_markdown]` table, and the folder of the
    `pyproject.toml` that holds it, from the nearest one at or above
    `start`."""
    here = (start or Path.cwd()).resolve()
    for folder in [here, *here.parents]:
        config = folder / "pyproject.toml"
        if not config.is_file():
            continue
        table = tomllib.loads(config.read_text()).get("tool", {})
        found = table.get("controlled_markdown")
        if found:
            return folder, found
    return here, {}


def configured(start: Path | None = None) -> list[str]:
    """The paths the table names, relative to the file that names them."""
    folder, table = _table(start)
    return [str(folder / name) for name in table.get("paths", [])]


def code_files(start: Path | None = None) -> list[Path]:
    """The code files the table names. A link in one resolves; nothing else
    in them is read as a document."""
    folder, table = _table(start)
    return [folder / name for name in table.get("code", [])]


def collect(names: list[str]) -> list[Path]:
    """The files the given paths name, a directory as every `.md` under it."""
    out: list[Path] = []
    for name in names:
        path = Path(name)
        out.extend(sorted(path.rglob("*.md")) if path.is_dir() else [path])
    return out


def shown(path: Path) -> str:
    """A path as the current directory sees it, or as given when it lies
    outside."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def check_code(paths: list[Path]) -> int:
    """Every link a code file holds resolves. The rest of the file is code,
    so nothing else in it is read."""
    off = 0
    for path in paths:
        if not path.is_file():
            continue
        try:
            check_text_links(path.read_text(), path, shown(path))
        except NestedMarkdownError as err:
            print(err)
            off += 1
    return off


def check(paths: list[Path]) -> int:
    off = 0
    for path in paths:
        name = shown(path)
        text = path.read_text()
        try:
            document = parse(text, name)
            check_blocks(document)
            check_links(document, path)
            # The registry claims the ids, so a repeat is reported here.
            Registry(Path.cwd()).add(name, document, name)
        except NestedMarkdownError as err:
            print(err)
            off += 1
            continue
        if write(document) != text:
            print(f"{name}: not in canonical form")
            off += 1
    return off


def fmt(paths: list[Path]) -> int:
    for path in paths:
        name = shown(path)
        text = path.read_text()
        try:
            document = parse(text, name)
        except NestedMarkdownError as err:
            print(err)
            return 1
        out = write(document)
        if out != text:
            path.write_text(out)
            print(name)
    return 0


def show(paths: list[Path]) -> int:
    registry = Registry(Path.cwd())
    documents = [registry.load(path, name=shown(path)) for path in paths]
    print(render(documents[0], registry), end="")
    return 0


def main(argv: list[str]) -> int:
    usage = (f"usage: {argv[0]} check|fmt [paths...]\n"
             f"       {argv[0]} render <path> [paths...]")
    command, names = (argv[1] if argv[1:] else ""), argv[2:]
    if command not in ("check", "fmt", "render"):
        print(usage, file=sys.stderr)
        return 2
    if not names:
        names = [] if command == "render" else configured()
    if not names:
        print(usage, file=sys.stderr)
        return 2
    paths = collect(names)
    code = code_files() if command == "check" and not argv[2:] else []
    try:
        if command == "check":
            return 1 if check(paths) + check_code(code) else 0
        if command == "fmt":
            return fmt(paths)
        return show(paths)
    except NestedMarkdownError as err:
        print(err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(["python -m controlled_markdown", *sys.argv[1:]]))
