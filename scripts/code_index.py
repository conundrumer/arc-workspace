"""Print the index of the packages that hold a set of files, or the list of
the packages of the tree. `HELP`, which `--help` prints, gives the usage
forms and what a package is."""

import argparse
import ast
import re
import sys
import textwrap
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from controlled_markdown import gist, mctx
from engine import checkout
from handbook.lib import lib_entries
from handbook.paths import scripts_importable

scripts_importable()

from path_args import refuse_absolute  # noqa: E402
from transcript_snapshots import Refused, print_refused  # noqa: E402

HELP = mctx("""
    - Usage: `uv run python scripts/code_index.py [<path> ...]`
    - `<path>` is the path of a file or a directory from the root of the tree.
    - With a `<path>`, the command prints, for each package that holds a `<path>` or is one, once each, the package's path, then one line per module of the package: the module's path from the package, the first sentence of its docstring, and its public names.
        - A Python module's docstring is its module docstring, and its public names are the names its `__all__` gives, or, where it gives none, the names its top-level `def`, `class`, `type` and assignment statements bind, other than those that start with `_`.
        - A Rust module's docstring is its `//!` lines, and its public names are those of its `pub` and `pub(crate)` items, at the top level and in its `impl` blocks, the latter as `<type>::<name>`.
        - A Souffle module prints as the lib's interface gives a lib file.
    - With no `<path>`, the command prints one line per package of the tree: its path and the first sentence of its docstring, the docstring of its `__init__.py` or of its `lib.rs`.
    - The packages of the tree:
        - each directory directly under `src/`, with the Python modules under it;
        - `src/` itself, with the Python modules directly in it;
        - `scripts/`, with the Python modules directly in it;
        - the `src/` directory of each Rust crate under `engine/`, a directory there that holds a `Cargo.toml`, with the Rust modules under it;
        - `programs/lib/`, with the Souffle modules directly in it.
    - A `<path>` in no package, such as one under `tests/`, `tools/` or `work/`, prints a line that says so.
    - The command refuses an absolute `<path>`.
    """)

PACKAGE = mctx("Package `{package}`:")
MODULE = mctx("- `{module}`")
MODULE_TEXT = mctx("- `{module}`: {text}")
NAMES = mctx("Names: {names}.")
NO_PACKAGE = mctx("`{path}` is in no package.")


class Language(Enum):
    PYTHON = ".py"
    RUST = ".rs"
    SOUFFLE = ".dl"


# The module whose docstring is its package's docstring. A Souffle package
# has none.
HEAD = {Language.PYTHON: "__init__.py", Language.RUST: "lib.rs"}


@dataclass(frozen=True)
class Package:
    root: Path
    """The package's directory, from the root of the tree."""
    language: Language
    recursive: bool
    """Whether the modules of the directories under `root` are the package's."""

    def holds(self, path: Path) -> bool:
        if path == self.root:
            return True
        if self.recursive:
            return path.is_relative_to(self.root)
        return path.parent == self.root and path.suffix == self.language.value

    def modules(self, tree: Path) -> list[Path]:
        pattern = f"*{self.language.value}"
        found = (tree / self.root).rglob(pattern) if self.recursive else (tree / self.root).glob(pattern)
        return sorted(p for p in found if "__pycache__" not in p.parts)


def packages(tree: Path) -> list[Package]:
    """The packages of the tree, in the order of their paths."""
    src = tree / "src"
    out = [Package(Path("src"), Language.PYTHON, False),
           Package(Path("scripts"), Language.PYTHON, False),
           Package(Path("programs/lib"), Language.SOUFFLE, False)]
    out += [Package(d.relative_to(tree), Language.PYTHON, True)
            for d in src.iterdir() if d.is_dir() and d.name != "__pycache__"]
    out += [Package((c.parent / "src").relative_to(tree), Language.RUST, True)
            for c in (tree / "engine").glob("*/Cargo.toml")]
    return sorted(out, key=lambda p: p.root)


@dataclass(frozen=True)
class Summary:
    doc: str | None
    """The first sentence of the module's docstring."""
    names: list[str]


def python_summary(text: str) -> Summary:
    tree = ast.parse(text)
    doc = ast.get_docstring(tree)
    names: list[str] = []
    for node in tree.body:
        match node:
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                names.append(node.name)
            case ast.TypeAlias(name=ast.Name(id=name)):
                names.append(name)
            case ast.Assign(targets=targets):
                names += [t.id for t in targets if isinstance(t, ast.Name)]
            case ast.AnnAssign(target=ast.Name(id=name)):
                names.append(name)
    exported = next((node.value for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)), None)
    if isinstance(exported, (ast.List, ast.Tuple)):
        names = [e.value for e in exported.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    else:
        names = [n for n in names if not n.startswith("_")]
    return Summary(_first_sentence(doc), names)


RUST_DOC = re.compile(r"^//!\s?(.*)$")
RUST_VISIBLE = r"pub(?:\(crate\))?\s+(?:(?:const|async|unsafe|extern\s+\"[^\"]*\")\s+)*"
RUST_ITEM = re.compile(r"^" + RUST_VISIBLE + r"(?:fn|struct|enum|union|trait|type|const|static|mod)\s+(\w+)")
RUST_METHOD = re.compile(r"^\s+" + RUST_VISIBLE + r"(?:fn|const|type)\s+(\w+)")
RUST_IMPL = re.compile(r"^impl\b")


def _impl_type(line: str) -> str:
    """The type an `impl` line at the top level of a file is for."""
    rest = line[len("impl"):].lstrip()
    if rest.startswith("<"):
        depth = 0
        for i, ch in enumerate(rest):
            depth += {"<": 1, ">": -1}.get(ch, 0)
            if depth == 0:
                rest = rest[i + 1:]
                break
    rest = re.split(r"\s+for\s+", rest, maxsplit=1)[-1]
    head = re.match(r"\s*([\w:]+)", rest)
    return head.group(1).split("::")[-1] if head else rest.strip()


def rust_summary(text: str) -> Summary:
    doc: list[str] = []
    names: list[str] = []
    impl: str | None = None
    for line in text.splitlines():
        if m := RUST_DOC.match(line):
            doc.append(m.group(1))
        elif RUST_IMPL.match(line):
            impl = _impl_type(line)
            if line.rstrip().endswith("}"):
                impl = None
        elif line.startswith("}"):
            impl = None
        elif m := RUST_ITEM.match(line):
            names.append(m.group(1))
        elif impl is not None and (m := RUST_METHOD.match(line)):
            names.append(f"{impl}::{m.group(1)}")
    return Summary(_first_sentence("\n".join(doc)), names)


def _first_sentence(doc: str | None) -> str | None:
    para = (doc or "").strip().split("\n\n")[0]
    return gist(para) if para else None


SUMMARIES = {Language.PYTHON: python_summary, Language.RUST: rust_summary}


def _row(module: str, summary: Summary) -> str:
    names = NAMES.format(names=", ".join(f"`{n}`" for n in summary.names)) if summary.names else None
    parts = [p for p in (summary.doc, names) if p]
    return MODULE_TEXT.format(module=module, text=" ".join(parts)) if parts else MODULE.format(module=module)


def module_lines(package: Package, path: Path, tree: Path) -> list[str]:
    module = path.relative_to(tree / package.root).as_posix()
    text = path.read_text()
    if package.language is Language.SOUFFLE:
        return [MODULE.format(module=module),
                *("    " + line for line in lib_entries(text).splitlines() if line.strip())]
    return [_row(module, SUMMARIES[package.language](text))]


def index(package: Package, tree: Path) -> str:
    return "\n".join([PACKAGE.format(package=package.root.as_posix()),
                      *(line for path in package.modules(tree)
                        for line in module_lines(package, path, tree))])


def package_list(tree: Path) -> str:
    rows = []
    for package in packages(tree):
        head = HEAD.get(package.language)
        path = tree / package.root / head if head else None
        doc = (SUMMARIES[package.language](path.read_text()).doc
               if path is not None and path.is_file() else None)
        rows.append(MODULE_TEXT.format(module=package.root.as_posix(), text=doc) if doc
                    else MODULE.format(module=package.root.as_posix()))
    return "\n".join(rows)


def code_index(paths: list[str], tree: Path = checkout.ROOT) -> str:
    refuse_absolute(paths, "code_index")
    if not paths:
        return package_list(tree)
    known = packages(tree)
    held: list[Package] = []
    strays: list[str] = []
    for p in paths:
        path = Path(p.rstrip("/"))
        owner = next((k for k in known if k.holds(path)), None)
        if owner is None:
            strays.append(NO_PACKAGE.format(path=p))
        elif owner not in held:
            held.append(owner)
    return "\n\n".join([*strays, *(index(k, tree) for k in held)])


def main() -> int:
    parser = argparse.ArgumentParser(description=textwrap.dedent(HELP),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", metavar="path")
    args = parser.parse_args()
    try:
        print(code_index(args.paths))
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
