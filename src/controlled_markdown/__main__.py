"""Check, format, and render Controlled Markdown documents.

    uv run python -m controlled_markdown check [paths...]   # report what is off
    uv run python -m controlled_markdown fmt [paths...]     # rewrite in canonical form
    uv run python -m controlled_markdown render <path> [paths...]

`check` reports each file that fails to parse or is not in canonical form, and
exits 1 when any does. A run given no path also counts, over the whole set, the
sites each partial is inlined at. `fmt` rewrites each file in canonical form
and prints the ones it changed. With no path, both read the set under
`[tool.controlled_markdown]` in `pyproject.toml`, so the command that guards the
documents is one word wherever it is written. `render` prints the first path as
ordinary Markdown, with its includes resolved from the files they name, and it
takes its paths as given. A path that names a directory stands for every `.md`
file under it. A name in a message is relative to the current directory.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

from . import (
    ControlledMarkdownError,
    Node,
    Registry,
    check_blocks,
    check_closure,
    check_dl_comments,
    check_file_fragments,
    check_links,
    check_partial_sites,
    check_paths,
    check_quote_rule,
    check_quotes,
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


# Where a program's prose can stand.
CODE_SUFFIXES = (".py", ".js", ".mjs")


def code_files(root: Path) -> list[Path]:
    """Every file under the root that a program's prose can stand in: each
    file git lists there as tracked, or as untracked and not ignored, so
    that what git ignores is skipped. A root that is no git tree is a
    fault."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, text=True, check=True).stdout
    return sorted(path for name in listed.split("\0")
                  if name.endswith(CODE_SUFFIXES) and (path := root / name).is_file())


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
    """Every fragment a program holds, read as the format, every document
    it names by path, and every handbook passage it quotes. The rest of each
    file is code, so nothing else in it is read."""
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
        if path.suffix == ".py":
            for err in check_quotes(path, shown(path)):
                print(err)
                off += 1
    for err in check_quote_rule(shown):
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


# Where the handbook starts: the composition, the two agent documents, and
# the session document, which inlines the operations its passes run.
HANDBOOK_ENTRIES = ("prompts/handbook.md", "prompts/agents/handbook.md",
                    "prompts/agents/handbook-expanded.md",
                    "prompts/agents/analyze.md", "prompts/agents/create.md",
                    "prompts/agents/refine.md",
                    "prompts/agents/analyze-next.md", "prompts/session.md")


def check_handbook(root: Path, document_set: set[Path]) -> int:
    """The rendered handbook links only where its reader can follow."""
    entries = [root / name for name in HANDBOOK_ENTRIES]
    try:
        check_closure([e for e in entries if e.is_file()], document_set, root)
    except ControlledMarkdownError as err:
        print(err)
        return 1
    return 0


def check(paths: list[Path], whole: bool = True) -> int:
    """Every document the paths name. `whole` says the paths are the document
    set, which is what the partial-sites rule counts over."""
    off = 0
    root = repo_root()
    parsed: list[tuple[Path, Node]] = []
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
        parsed.append((path.resolve(), document))
        if write(document) != text:
            print(f"{name}: not in canonical form")
            off += 1
    if whole:
        # The rule counts the sites in every document, so it runs once the
        # whole set is parsed.
        for err in check_partial_sites(parsed):
            print(err)
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
            whole = not argv[2:]
            off = check(paths, whole)
            if whole:
                root = repo_root()
                document_set = {p.resolve() for p in paths}
                off += check_code(root, document_set)
                off += check_handbook(root, document_set)
            if off:
                return 1
            word = "document" if len(paths) == 1 else "documents"
            print(f"check: {len(paths)} {word}, ok")
            return 0
        if command == "fmt":
            return fmt(paths)
        return show(paths)
    except ControlledMarkdownError as err:
        print(err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(["python -m controlled_markdown", *sys.argv[1:]]))
