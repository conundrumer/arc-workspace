"""The reference context a solver session reads, projected down to what the
cadence uses.

`lib.dl` renders as signatures, and the catalog docs render as one line per
entry; both name the file that holds the rest. The other docs pass through
whole. Every rendering derives from the live file, so no copy can go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

from dl.paths import PROGRAMS_DIR, REPO_ROOT

DOCS_DIR = REPO_ROOT / "docs" / "wf-solver"
LIB_SRC = PROGRAMS_DIR / "lib.dl"

# Reading order: the claim, then its form, then what the corpus made of it.
# A doc not listed follows, by name.
ORDER = ("principles.md", "style.md", "patterns.md", "concepts.md", "proposals.md")
# Docs the cadence never reads.
SKIP = {"backlog.md"}
# Catalog docs: entries are independent and a session uses few, so the context
# carries the index and the session reads the entry it needs.
INDEX = {"patterns.md", "proposals.md"}

DECL_HEAD = (".type", ".decl", ".comp", ".init", "#define", "}")

LIB_PREAMBLE = """\
// Signatures only: rule bodies are dropped, and the facts of a top-level
// lookup relation stand described by its comment. Inside a component, a
// `.decl` marked `// input` is one the solver populates; the rest derive.
// Read programs/lib.dl for a body.

"""


def lib_signatures(text: str) -> str:
    """lib.dl as its interface: comments, types, macros, .decl signatures,
    component structure, and the default fills components carry."""
    out: list[str] = []
    stmt: list[str] = []   # body lines of the .decl still open
    decl_at = -1           # index in `out` of that .decl
    in_comp = False
    open_parens = 0        # unclosed parens of a wrapped .decl

    def flush() -> None:
        nonlocal stmt, decl_at
        if decl_at >= 0 and not stmt:
            out[decl_at] += "  // input"
        if in_comp and stmt and not any(":-" in s for s in stmt):
            out.extend(stmt)   # a component's default fill is its data
        stmt, decl_at = [], -1

    for line in text.splitlines():
        s = line.strip()
        if open_parens:
            out.append(line)
            open_parens += s.count("(") - s.count(")")
            continue
        if not s or s.startswith("//") or s.startswith(DECL_HEAD):
            flush()
            if s.startswith(".comp"):
                in_comp = True
            elif s == "}":
                in_comp = False
            out.append(line)
            if s.startswith(".decl"):
                open_parens = s.count("(") - s.count(")")
                decl_at = len(out) - 1
            continue
        stmt.append(line)
    flush()
    return LIB_PREAMBLE + re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


def gist(para: str, floor: int = 130, cap: int = 2) -> str:
    """An entry's opening sentences, to the first one that both carries the
    claim and closes it. One sentence carries an entry when it is long enough
    to state the whole claim; past `cap` the detail belongs to the entry."""
    said: list[str] = []
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z`\"(])", para):
        said.append(sentence)
        text = " ".join(said)
        if (len(text) >= floor or len(said) >= cap) and not text.endswith(":"):
            return text
    return " ".join(said)


def entry_index(text: str, source: str) -> str:
    """A `## ` catalog doc as its preamble and one line per entry. The
    preamble says what the doc is, which every entry stands on."""
    blocks = re.split(r"^## ", text, flags=re.M)
    preamble = "\n\n".join(p for p in blocks[0].split("\n\n")[1:] if p.strip())
    out: list[str] = []
    for block in blocks[1:]:
        title, _, rest = block.partition("\n")
        body = re.sub(r"```.*?```", "", rest, flags=re.S)
        opening = ""
        for para in body.split("\n\n"):
            para = " ".join(para.split())
            if para and not para.startswith(("#", "-", "|", "*")):
                opening = gist(para)
                break
        out.append(f"- **{title.strip()}** — {opening}" if opening
                   else f"- **{title.strip()}**")
    note = f"One line per entry. Read {source} for the entries you need."
    return "\n\n".join(p for p in (preamble.strip(), note, "\n".join(out)) if p) + "\n"


def appendix(docs: Path = DOCS_DIR, lib: Path = LIB_SRC) -> str:
    """Every doc and lib.dl, each under a heading naming its file."""
    parts: list[str] = []
    ranked = sorted(docs.glob("*.md"),
                    key=lambda d: (ORDER.index(d.name) if d.name in ORDER
                                   else len(ORDER), d.name))
    for doc in ranked:
        if doc.name in SKIP:
            continue
        rel = f"docs/wf-solver/{doc.name}"
        if doc.name in INDEX:
            parts.append(f"\n---\n\n# {rel} — index\n\n"
                         f"{entry_index(doc.read_text(), rel)}")
        else:
            parts.append(f"\n---\n\n# {rel}\n\n{doc.read_text()}")
    parts.append("\n---\n\n# programs/lib.dl — signatures\n\n"
                 f"```\n{lib_signatures(lib.read_text())}```\n")
    return "".join(parts)
