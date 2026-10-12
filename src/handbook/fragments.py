"""The `fragments <part>` reader's context: the text of each `mctx` fragment
of one part of the code, `scripts` or a package under `src/`, which the
standing doc review reads as it reads a document."""

from __future__ import annotations

from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from handbook.paths import DOCUMENTS_ROOT, repo_label

SCRIPTS_PART = "scripts"
"""The part that holds the scripts under `scripts/`. Each other part is a
package under `src/`, by its directory's name."""


def _part_dirs(root: Path) -> dict[str, Path]:
    return {SCRIPTS_PART: root / "scripts",
            **{d.name: d for d in sorted((root / "src").iterdir())
               if d.is_dir()}}


def _modules(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _holds_fragment(path: Path) -> bool:
    return any(True for _ in nm.fragments(path, repo_label(path)))


def fragment_parts(root: Path) -> list[str]:
    """Each part under `root` whose Python modules hold an `mctx` fragment."""
    return [part for part, directory in _part_dirs(root).items()
            if any(_holds_fragment(path) for path in _modules(directory))]


def fragments_context(part: str) -> str:
    """Each fragment of the part's Python modules, in file and line order,
    each under a line that gives its path and line, with each hole as the
    source writes it."""
    parts = fragment_parts(DOCUMENTS_ROOT)
    if part not in parts:
        raise SystemExit(mctx("`{part}` is not a part: the parts are {parts}")
                         .format(part=part, parts=", ".join(parts)))
    texts = (file_fragments_text(path)
             for path in _modules(_part_dirs(DOCUMENTS_ROOT)[part]))
    return "\n\n".join(text for text in texts if text) + "\n"


def file_fragments_text(path: Path) -> str:
    """Each `mctx` fragment of one file, in line order, each under a line
    that gives the file and the line the fragment starts on."""
    label = repo_label(path)
    return "\n\n".join(f"{label}:{fragment.line}\n\n{fragment.text.rstrip()}"
                       for fragment in sorted(nm.fragments(path, label),
                                              key=lambda f: f.line))
