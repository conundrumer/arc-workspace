"""Which converted solvers use each lib name and each form keyword, so that
a check of a change runs first the solvers the change's parts reach: a scan
of the arclog files under `work/arclog/gen/`, written to `uses.json` beside
the records (`parity.snapshot.parity_dir`)."""

import json
import re
from functools import cache
from pathlib import Path

from engine import ParseFailure, checkout
from parity.snapshot import parity_dir
from souffle import SouffleEngine

KEYWORD_RE = re.compile(r"[A-Z][A-Z_]+")
"""A form keyword as an arclog form's head writes it: `DET`, `INIT`. A
head of one capital letter opens a list of variables, `(A N)`."""

HEAD_RE = re.compile(r"\((?P<head>[^\s()\"]+)")
"""The head of a form."""

INIT_RE = re.compile(r"\(INIT\s+\S+\s+(?P<component>\w+)")
"""The component an `INIT` form makes an instance of."""

COMMENT_RE = re.compile(r";[^\n]*")
STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def gen_dir() -> Path:
    """`work/arclog/gen/` of the main worktree."""
    return checkout.work() / "arclog" / "gen"


def signature_path() -> Path:
    """The signature of the lib the converter writes against."""
    return checkout.work() / "arclog" / "lib-signature.dl"


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


def used(text: str) -> set[str]:
    """The lib names and the form keywords the arclog `text` reads."""
    text = STRING_RE.sub('""', COMMENT_RE.sub("", text))
    libs = lib_names()
    heads = {m["head"] for m in HEAD_RE.finditer(text)}
    return {h for h in heads if KEYWORD_RE.fullmatch(h) or h in libs} \
        | {m["component"] for m in INIT_RE.finditer(text) if m["component"] in libs}


def uses() -> dict[str, list[str]]:
    """Each lib name and each form keyword a file of `work/arclog/gen/`
    reads, with the stems of the files that read it, both sorted."""
    out: dict[str, set[str]] = {}
    for path in sorted(gen_dir().glob("*.arclog")):
        for name in used(path.read_text()):
            out.setdefault(name, set()).add(path.stem)
    return {name: sorted(out[name]) for name in sorted(out)}


def write_all() -> Path:
    """Write `uses` to `uses.json`, and give its path."""
    path = uses_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(uses(), indent=1) + "\n")
    return path
