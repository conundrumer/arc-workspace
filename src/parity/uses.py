"""Which converted solvers use each lib name, each proposer and each form
keyword, so that
a check of a change runs first the solvers the change's parts reach: a scan
of the arclog files under `work/arclog/gen/`, written to `uses.json` beside
the records (`parity.snapshot.parity_dir`)."""

import json
import re
from functools import cache
from pathlib import Path

import arclog_convert
from arclog_convert.readback import read_checked
from engine import ParseFailure, checkout
from parity.snapshot import parity_dir
from solver.readers import proposer_names, proposers_program
from souffle import SouffleEngine

KEYWORD_RE = re.compile(r"[A-Z][A-Z_]+")
"""A form keyword as an arclog form's head writes it: `DET`, `INIT`. A
head of one capital letter opens a list of variables, `(A N)`."""

HEAD_RE = re.compile(r"\((?P<head>[^\s()\"]+)")
"""The head of a form."""

TOKEN_RE = re.compile(r"[^\s()\"]+")
"""A bare token of a form. A proposer or a lib component is written as
one capitalized token, in any form; an alt name opens with `$`, and a
relation or an instance with `&` (docs/arclog/arclog.md, under "Names")."""

QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"|;[^\n]*')
"""A string or a comment, whichever opens first, so that a `;` inside a
string opens no comment and a `"` inside a comment opens no string."""


def gen_dir() -> Path:
    """`work/arclog/gen/` of the main worktree."""
    return checkout.work() / "arclog" / "gen"


def signature_path() -> Path:
    """The signature of the lib the converter writes against."""
    return arclog_convert.signature()


def uses_path() -> Path:
    """`uses.json` beside the records."""
    return parity_dir() / "uses.json"


@cache
def lib_names() -> frozenset[str]:
    """The top-level relations and the components the lib signature
    declares."""
    path = signature_path()
    prog = SouffleEngine().parse(path.read_text(), path.parent)
    if isinstance(prog, ParseFailure):
        raise ValueError(f"{path} does not parse: {prog}")
    return frozenset({r.name for r in prog.relations if not r.scope.components}
                     | {c.name for c in prog.components})


@cache
def proposers() -> frozenset[str]:
    """The proposers of `programs/proposers.dl` (`solver.readers.proposer_names`)."""
    prog = proposers_program(SouffleEngine())
    if isinstance(prog, ParseFailure):
        raise ValueError(f"programs/proposers.dl does not parse: {prog}")
    return frozenset(proposer_names(prog))


def used(text: str) -> set[str]:
    """The lib names, the proposers and the form keywords the arclog `text`
    names: a lib relation as a form's head, a keyword as a form's head, and
    a lib component or a proposer as any capitalized token. A claim slug is
    a bare lowercase token as well, so a lib relation counts only as a
    head."""
    text = QUOTED_RE.sub(lambda m: '""' if m[0].startswith('"') else "", text)
    libs = lib_names()
    heads = {m["head"] for m in HEAD_RE.finditer(text)}
    tokens = {t for t in TOKEN_RE.findall(text)
              if t[:1].isupper() and not KEYWORD_RE.fullmatch(t)}
    return {h for h in heads if KEYWORD_RE.fullmatch(h) or h in libs} \
        | {t for t in tokens if t in libs or t in proposers()}


def uses() -> dict[str, list[str]]:
    """Each lib name, each proposer and each form keyword a file of
    `work/arclog/gen/` names (`used`), with the stems of the files that
    name it, both sorted. Each file is read through `arclog_convert.readback.read_checked`."""
    out: dict[str, set[str]] = {}
    for path in sorted(gen_dir().glob("*.arclog")):
        for name in used(read_checked(path)):
            out.setdefault(name, set()).add(path.stem)
    return {name: sorted(out[name]) for name in sorted(out)}


def write_all() -> Path:
    """Write `uses` to `uses.json`, and give its path."""
    path = uses_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(uses(), indent=1) + "\n")
    return path
