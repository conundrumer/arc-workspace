"""The import rule among the packages under `src/`. An import across a
forbidden edge runs as well as any other, so no run shows it."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

PACKAGES = frozenset({"engine", "souffle", "solver", "checker", "cli",
                      "handbook"})
"""The packages the rule speaks of. `arc` and `controlled_markdown` stand
outside it, and any package may import them."""

ALLOWED: dict[str, frozenset[str]] = {
    "engine": frozenset({"engine"}),
    "souffle": frozenset({"souffle", "engine"}),
    "solver": frozenset({"solver", "engine"}),
    "checker": frozenset({"checker", "solver", "engine"}),
    "cli": PACKAGES,
    "handbook": PACKAGES,
}
"""For each package the rule constrains, the packages it may import."""

REFUSED = frozenset({"dl", "study", "tools"})
"""The old tree, the study scripts and the console, which none of the
packages the rule constrains may import."""

ABOVE = "<a relative import above its package>"


def imported(path: Path, package: str) -> list[tuple[int, str]]:
    """The top-level package each import statement of `path`, a module of
    `package`, names, with the statement's line. A relative import names
    `package`, or `ABOVE` where it climbs out of it."""
    depth = len(path.relative_to(SRC / package).parts)
    out: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            out += [(node.lineno, alias.name.split(".")[0]) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module is not None:
                out.append((node.lineno, node.module.split(".")[0]))
            else:
                out.append((node.lineno, package if node.level <= depth else ABOVE))
    return out


def test_no_package_imports_across_a_forbidden_edge():
    edges = [f"{path.relative_to(SRC)}:{line} imports {name}"
             for package, allowed in ALLOWED.items()
             if (SRC / package).is_dir()
             for path in sorted((SRC / package).rglob("*.py"))
             for line, name in imported(path, package)
             if name == ABOVE or name in REFUSED
             or (name in PACKAGES and name not in allowed)]
    assert edges == []
