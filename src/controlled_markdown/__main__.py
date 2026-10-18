"""Check, format, and render Controlled Markdown documents.

    uv run python -m controlled_markdown check [paths...]   # report what is off
    uv run python -m controlled_markdown fmt [paths...]     # rewrite in canonical form
    uv run python -m controlled_markdown render <path> [paths...]
    uv run python -m controlled_markdown xrefs <base> [paths...]

`check` reports each file that fails to parse or is not in canonical form,
each target of an `xref` attribute that names nothing, each script,
module or path a backticked span names that the tree does not hold
(`controlled_markdown.xrefs`), and each line whose own words hold a form
of `carry` of a document, of an `mctx` fragment, of a lib doc comment, or of a docstring or a comment of a
Python file outside `tools/console/`, and exits 1 when any does. A run
given no path also counts, over the whole set, the sites each partial is
inlined at. `fmt` rewrites each file in canonical form and prints the ones
it changed. With no path, both read the set under
`[tool.controlled_markdown]` in `pyproject.toml`, so the command that guards the
documents is one word wherever it is written. `render` prints the first path as
ordinary Markdown, with its includes resolved from the files they name, and it
takes its paths as given. `xrefs` prints, for each `xref` target, a file's
path, `<path>:<name>` for a definition in a Python file or `<path>#<slug>`
for a section of a document, whose lines the diff from the commit `base` to
the working tree changes, or that names nothing, one line `<path>:<line>: <target>: <text>`, with
the text of the statement the attribute describes, and exits 0; with no
path, it reads the set `check` reads. Run with the copy of this module in a
linked worktree, `xrefs` runs the main tree's copy under the main tree's
project, in the same directory and with the same arguments, and exits with
its status, or exits 2 where the main tree holds no such module. With no
path, in a linked worktree, it reads the main tree's copy of each document
of the set `check` reads in the main tree, and the worktree's copy of each
document of the worktree's set that the worktree's diff from `base` adds or
changes. `check`, `fmt` and `render` run the copy they are called with. A path that names a directory
stands for every `.md` file under it, and a path that names no file or directory is reported on one
line, with exit status 2. `-h` or `--help`, given as any argument, prints the
usage and exits 0. A name in a message is relative to the current directory.
"""

import errno
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from checker.quoting import quote_rule_errors

from . import (
    ControlledMarkdownError,
    Node,
    Registry,
    carry_errors,
    check_blocks,
    check_citation_anchors,
    check_citation_paths,
    check_citations,
    code_carry_errors,
    check_closure,
    check_dl_comments,
    check_file_fragments,
    check_links,
    check_partial_sites,
    check_paths,
    check_quotes,
    check_xrefs,
    parse,
    render,
    touched,
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


def main_tree(start: Path) -> Path:
    """The main tree of the git repository that holds `start`: the parent of
    its common git directory."""
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=start, capture_output=True, text=True, check=True).stdout.strip()
    return Path(common).parent.resolve()


def run_in_main(args: list[str], package: Path) -> int | None:
    """Runs the main tree's copy of this package with `args`, where `package`,
    the folder of the running copy, is another one, and returns its exit
    status; None where `package` is the main tree's copy. The environment
    drops `VIRTUAL_ENV`, so the run takes the main tree's own environment."""
    main = main_tree(package)
    copy = main / "src" / "controlled_markdown"
    if package.resolve() == copy.resolve():
        return None
    if not (copy / "__main__.py").is_file():
        print(f"{main}: the main tree has no `src/controlled_markdown`", file=sys.stderr)
        return 2
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    return subprocess.run(["uv", "run", "--project", str(main), "python", "-m",
                           "controlled_markdown", *args], env=env).returncode


def changed_files(root: Path, base: str) -> set[str]:
    """Each file the diff from the commit `base` to the working tree at
    `root` adds or changes, and each untracked file git does not ignore, by
    its path from `root`."""
    def listed(*argv: str) -> list[str]:
        return subprocess.run(["git", *argv], cwd=root, capture_output=True,
                              text=True, check=True).stdout.split("\0")
    return {name for name in [*listed("diff", "--name-only", "-z", base),
                              *listed("ls-files", "--others", "--exclude-standard", "-z")]
            if name and (root / name).is_file()}


def xrefs_documents(root: Path, base: str) -> list[Path]:
    """The documents `xrefs` reads with no path: the set `check` reads, in a
    linked worktree at `root` the main tree's copies, apart from the
    worktree's copy of each document of its own set that its diff from
    `base` adds or changes."""
    main = main_tree(root)
    if main == root.resolve():
        return collect(configured(root))
    changed = changed_files(root, base)
    ours = {p.resolve().relative_to(root.resolve()).as_posix()
            for p in collect(configured(root))} & changed
    theirs = [p for p in collect(configured(main))
              if p.resolve().relative_to(main).as_posix() not in changed]
    return theirs + [root / name for name in sorted(ours)]


# Where a program's prose can stand.
CODE_SUFFIXES = (".py", ".js", ".mjs")


def present_files(root: Path) -> frozenset[str]:
    """Every file under the root that git lists as tracked, or as untracked
    and not ignored, and the tree holds, by its path as git writes it: the
    files a commit of the tree takes, since the merge stages the whole tree
    before its checks. A root that is no git tree is a fault."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, text=True, check=True).stdout
    return frozenset(name for name in listed.split("\0")
                     if name and (root / name).is_file())


def code_files(root: Path) -> list[Path]:
    """Every file of `present_files` that a program's prose can stand in."""
    return sorted(root / name for name in present_files(root)
                  if name.endswith(CODE_SUFFIXES))


# The tree whose citations name only files a commit of the tree takes.
ENGINE = "engine/"


def collect(names: list[str]) -> list[Path]:
    """The files the given paths name, a directory as every `.md` under it."""
    out: list[Path] = []
    for name in names:
        path = Path(name)
        if not path.exists():
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), name)
        out.extend(sorted(path.rglob("*.md")) if path.is_dir() else [path])
    return out


def shown(path: Path) -> str:
    """A path as the current directory sees it, or as given when it lies
    outside."""
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


# The Souffle files whose doc comments an agent reads: the lib's, and the
# proposers', whose comments the `analyze` context lists.
DL_DOC_GLOBS = ("programs/lib.dl", "programs/lib/*.dl", "programs/proposers.dl")


def check_code(root: Path, document_set: set[Path]) -> int:
    """Every fragment a program holds, read as the format, every document
    it names by path, every handbook passage it quotes, every file and
    section the engine cites, every section other code cites, and every
    document a Python docstring or comment cites by its file name alone.
    The rest of each file is code, so nothing else in it is read."""
    off = 0
    present = present_files(root)
    for name in sorted(present):
        if name.startswith(ENGINE):
            path = root / name
            for err in check_citations(path, shown(path), root, present):
                print(err)
                off += 1
    for path in code_files(root):
        if not path.relative_to(root).as_posix().startswith(ENGINE):
            for err in check_citation_anchors(path, shown(path), root):
                print(err)
                off += 1
        for err in check_citation_paths(path, shown(path), present):
            print(err)
            off += 1
        try:
            check_file_fragments(path, shown(path), root)
            # A test names the paths it makes up, so a name there stands for a
            # shape and not for a document in the tree.
            if "tests" not in path.relative_to(root).parts:
                check_paths(path, shown(path), root)
        except ControlledMarkdownError as err:
            print(err)
            off += 1
        for err in code_carry_errors(path, shown(path)):
            print(err)
            off += 1
        if path.suffix == ".py":
            for err in check_quotes(path, shown(path)):
                print(err)
                off += 1
    for err in quote_rule_errors(shown):
        print(err)
        off += 1
    for pattern in DL_DOC_GLOBS:
        for path in sorted(root.glob(pattern)):
            try:
                check_dl_comments(path, shown(path), root)
            except ControlledMarkdownError as err:
                print(err)
                off += 1
            for err in code_carry_errors(path, shown(path)):
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
            for err in carry_errors(document):
                print(err)
                off += 1
            check_blocks(document)
            check_links(document, path, root)
            for err in check_xrefs(document, root):
                print(err)
                off += 1
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


def show_touched(base: str, paths: list[Path]) -> int:
    """Each line whose `xref` target the diff from `base` changes."""
    documents = [parse(path.read_text(), shown(path)) for path in paths]
    for touch in touched(documents, repo_root(), base):
        print(f"{touch.node.source}:{touch.node.line}: {touch.target}: {touch.node.text}")
    return 0


def main(argv: list[str]) -> int:
    usage = (f"usage: {argv[0]} check|fmt [paths...]\n"
             f"       {argv[0]} render <path> [paths...]\n"
             f"       {argv[0]} xrefs <base> [paths...]\n"
             f"an xref target: <path>, <path>:<name> or <path>#<slug>")
    if argv[1:2] == ["xrefs"]:
        status = run_in_main(argv[1:], Path(__file__).parent)
        if status is not None:
            return status
    if {"-h", "--help"} & set(argv[1:]):
        print(usage)
        return 0
    command, names = (argv[1] if argv[1:] else ""), argv[2:]
    if command not in ("check", "fmt", "render", "xrefs"):
        print(usage, file=sys.stderr)
        return 2
    base = ""
    if command == "xrefs":
        if not names:
            print(usage, file=sys.stderr)
            return 2
        base, names = names[0], names[1:]
    whole = not names
    if whole and (command == "render" or not configured()):
        print(usage, file=sys.stderr)
        return 2
    if whole and command != "xrefs":
        names = configured()
    try:
        paths = (xrefs_documents(repo_root(), base) if whole and command == "xrefs"
                 else collect(names))
    except FileNotFoundError as err:
        print(f"{err.filename}: {err.strerror}", file=sys.stderr)
        return 2
    try:
        if command == "check":
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
        if command == "xrefs":
            return show_touched(base, paths)
        return show(paths)
    except ControlledMarkdownError as err:
        print(err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(["python -m controlled_markdown", *sys.argv[1:]]))
