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
    ControlledMarkdownError,
    Registry,
    check_blocks,
    check_closure,
    check_dl_comments,
    check_file_fragments,
    check_links,
    check_paths,
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


def repo_root(start: Path | None = None) -> Path:
    """The folder the config sits in, which a link's target stands from."""
    return _table(start)[0]


# Where a program's prose can stand. Everything else under the root is data,
# a build, or history.
CODE_SUFFIXES = (".py", ".js", ".mjs")
SKIPPED = {".venv", "node_modules", ".git", "data", ".scratch"}


def code_files(root: Path) -> list[Path]:
    """Every file under the root that a program's prose can stand in."""
    out = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in CODE_SUFFIXES or not path.is_file():
            continue
        if SKIPPED & set(path.relative_to(root).parts):
            continue
        out.append(path)
    return out


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


# The lib's Souffle files, whose doc comments an agent reads.
LIB_GLOBS = ("programs/lib.dl", "programs/lib/*.dl")


def check_code(root: Path, document_set: set[Path]) -> int:
    """Every fragment a program holds, read as the format, and every document
    it names by path. The rest of each file is code, so nothing else in it is
    read."""
    off = 0
    for path in code_files(root):
        try:
            check_file_fragments(path, shown(path), root)
            # A test names the paths it makes up, so a name there stands for a
            # shape and not for a document in the tree.
            if "tests" not in path.relative_to(root).parts:
                check_paths(path, shown(path), root)
        except ControlledMarkdownError as err:
            print(err)
            off += 1
    for pattern in LIB_GLOBS:
        for path in sorted(root.glob(pattern)):
            try:
                check_dl_comments(path, shown(path), root)
            except ControlledMarkdownError as err:
                print(err)
                off += 1
    return off


# Where the handbook starts: the composition and the two agent documents.
HANDBOOK_ENTRIES = ("prompts/handbook.md", "prompts/agents/handbook.md",
                    "prompts/agents/handbook-expanded.md")


def check_handbook(root: Path, document_set: set[Path]) -> int:
    """The rendered handbook links only where its reader can follow."""
    entries = [root / name for name in HANDBOOK_ENTRIES]
    try:
        check_closure([e for e in entries if e.is_file()], document_set, root)
    except ControlledMarkdownError as err:
        print(err)
        return 1
    return 0


def check(paths: list[Path]) -> int:
    off = 0
    root = repo_root()
    for path in paths:
        name = shown(path)
        text = path.read_text()
        try:
            document = parse(text, name)
            check_blocks(document)
            check_links(document, path, root)
            # The registry claims the ids, so a repeat is reported here.
            Registry(Path.cwd()).add(name, document, name)
        except ControlledMarkdownError as err:
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
        except ControlledMarkdownError as err:
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
    try:
        if command == "check":
            off = check(paths)
            if not argv[2:]:
                root = repo_root()
                document_set = {p.resolve() for p in paths}
                off += check_code(root, document_set)
                off += check_handbook(root, document_set)
            return 1 if off else 0
        if command == "fmt":
            return fmt(paths)
        return show(paths)
    except ControlledMarkdownError as err:
        print(err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(["python -m controlled_markdown", *sys.argv[1:]]))
