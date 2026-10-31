"""What the Souffle solver of an arclog file writes at the atoms that the file reads with no site (`bare_read_source`).

The arclog text keeps no map from an atom to a line of the solver, so the answer is per clause: the solver rules whose
head is the relation the clause derives (by the name map under `names/`), and their body atoms on the relation that the
atom reads. Where the file has no solver, no name map, or no rule that matches, the answer is `None`."""
from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from arclog_convert import paths

IDENT = re.compile(r"([A-Za-z_][\w.]*)\s*\(")

WILDCARD_ONLY = "wildcard-only"
CASE_FIXED = "case-fixed"
SINGLE_USE = "single-use"
NAMED = "named"
MIXED = "mixed"


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def split_args(inner: str) -> list[str]:
    args, depth, cur = [], 0, []
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur or args:
        args.append("".join(cur).strip())
    return args


def atoms_in(text: str) -> list[tuple[str, list[str]]]:
    """Each `name(args)` of `text` as (the last segment of the name, the arguments), the atoms nested in an argument
    included."""
    found = []
    for m in IDENT.finditer(text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        found.append((m.group(1).rpartition(".")[2], split_args(text[m.end():i - 1])))
    return found


def statements(text: str) -> list[str]:
    """The statements of a solver that hold a rule, by the `.` that ends a rule: one at nesting depth 0 that a space or the
    end follows. A line that starts a directive (`.decl`, `.init`, ...) is left out."""
    text = "\n".join(l for l in strip_comments(text).splitlines() if not re.match(r"\s*\.[A-Za-z]", l))
    out_, depth, start, in_str = [], 0, 0, False
    for i, ch in enumerate(text):
        if ch == '"':
            in_str = not in_str
        elif in_str:
            continue
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "." and depth == 0 and (i + 1 == len(text) or text[i + 1].isspace()):
            out_.append(text[start:i])
            start = i + 1
    return [s for s in out_ if ":-" in s]


def atom_kind(args: list[str], rule: str) -> str:
    """`wildcard-only` where every argument is `_` or the unit `$U()`; `single-use` where each is `_` or a name that stands once in the
    rule; `named` where one is a name the rule uses again, or a term."""
    kinds = []
    for a in args:
        if a in ("_", "$U()"):   # `$U()` is the unit: it holds no value
            kinds.append(WILDCARD_ONLY)
        elif re.fullmatch(r"[A-Za-z]\w*", a) and len(re.findall(rf"(?<![\w.]){a}(?![\w(])", rule)) == 1:
            kinds.append(SINGLE_USE)
        else:
            kinds.append(NAMED)
    return NAMED if NAMED in kinds else SINGLE_USE if SINGLE_USE in kinds else WILDCARD_ONLY


@cache
def solver_rules(stem: str) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...] | None:
    """Each rule of the solver as (the last segment of its head relation, its body atoms as (last segment of the
    relation, `atom_kind`)), or None without a solver."""
    path = paths.SOLVERS / f"{stem}.dl"
    if not path.exists():
        return None
    rules = []
    for st in statements(path.read_text()):
        head, _, body = st.partition(":-")
        hs = atoms_in(head)
        if hs:
            rules.append((hs[0][0], tuple((n, atom_kind(a, st)) for n, a in atoms_in(body))))
    return tuple(rules)


@cache
def kept_labels(stem: str) -> dict[str, list[list]] | None:
    """Each arclog relation's solver columns, as the column map keeps them: the leaves, with their labels, that the
    column maps onto in the arclog."""
    path = paths.COLUMNS_DIR / f"{stem}.json"
    if not path.exists():
        return None
    return {k: [col for cols in v.values() for col in cols] for k, v in json.loads(path.read_text()).items()}


@cache
def name_map(stem: str) -> dict[str, list[str]] | None:
    """Each arclog relation's solver relations, by the last segment of the name."""
    path = paths.NAMES_DIR / f"{stem}.json"
    if not path.exists():
        return None
    rels = json.loads(path.read_text()).get("relations", {})
    return {k: [v["relation"].rpartition(".")[2] for v in vs] for k, vs in rels.items()}


def bare_read_source(stem: str, clause: str | None, rel: str) -> str | None:
    """How the solver rules that derive `clause` (every rule, where none of them reads `rel`) write the relation
    `rel`, and where: "wildcard-only" where every argument of each atom is `_`; "single-use" where each argument is
    `_` or a name that stands once in its rule; "named" where each atom has a name that the rule uses again, or a
    term; "mixed" otherwise; "case-fixed" first, where the column map keeps no label of any column of the relation, because
    the case fixes them all. "in the clause" or "in the solver" says which rules the atoms are from. None where the
    solver or the name map does not say."""
    rules, names = solver_rules(stem), name_map(stem)
    kept = (kept_labels(stem) or {}).get(rel)
    if kept and not any(kept):
        return f"{CASE_FIXED}: no column of the solver's relation has a label in the arclog"
    if rules is None or names is None or rel not in names:
        return None
    heads = set(names.get(clause or "", ()))
    own = [r for r in rules if r[0] in heads]
    scope = "clause"
    kinds = [k for _, body in own for n, k in body if n in names[rel]]
    if not kinds:
        scope = "solver"
        kinds = [k for _, body in rules for n, k in body if n in names[rel]]
    if not kinds:
        return None
    if all(k == WILDCARD_ONLY for k in kinds):
        what = WILDCARD_ONLY
    elif NAMED not in kinds:
        what = SINGLE_USE
    else:
        what = NAMED if all(k == NAMED for k in kinds) else MIXED
    return f"{what} in the {scope}"
