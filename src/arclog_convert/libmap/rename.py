"""The renames of `REL`, `COMP` and `DERIVATIONS` over arclog, arcdata and
arcscene text, read with lint's reader: each other byte of the text stands.

- A lib relation's atom takes its new name, and each site its column's new
  name, elided to the bare label where the label is that name.
- Where the relation has a guard, an atom that leaves the guarded column
  out takes a site there with a fresh label, and an atom that leaves it
  out or makes its label at that site, with `*` or `^`, is followed by the
  guard relation's atom on that label, so the site keeps the present type.
- An `INIT` of a renamed component takes the new name and each input's new
  name, unless the text reads an output of the instance that `keep` names.
- A read `&<inst>.<output>` of such an instance takes the output's new name.
- A derivation's name in a `DET` line or a `param` form takes its new name,
  unless the table's stored values hold a field the new name lacks.
"""
from __future__ import annotations

import re

from arclog_convert.libmap import COMP, DERIVATIONS, REL

READ = re.compile(r"^(\^|\*)?(&[a-z_0-9]+)\.([a-z_0-9]+)(.*)$")


def instances(text: str) -> dict[str, str]:
    """Each instance the text's `INIT` forms make, with its component."""
    from arclog_convert.lint import L, Sym, read
    out: dict[str, str] = {}

    def scan(xs):
        for x in xs:
            if isinstance(x, L):
                if x.head == "INIT" and len(x.items) >= 3 and isinstance(x.items[2], Sym):
                    out[x.items[1].text] = x.items[2].text
                scan(x.items)
    scan(read(text))
    return out


def reads(text: str) -> set[tuple[str, str]]:
    """Each (instance, relation) the text reads by `&<inst>.<relation>`."""
    return {(m[2], m[3]) for m in map(READ.match, re.findall(r"[\^*]?&[a-z_0-9]+\.[a-z_0-9]+", text)) if m}


def renamed_instances(insts: dict[str, str], read: set[tuple[str, str]]) -> dict[str, str]:
    """The instances the renames apply to, with their present component."""
    return {i: c for i, c in insts.items()
            if c in COMP and not any((i, r) in read for r in COMP[c].keep)}


def site_text(col: str, label: str) -> str:
    return label if label.lstrip("*^") == col else f"(:{col} {label})"


def fresh(base: str, taken: set[str]) -> str:
    """`base`, or `base` with the least number appended, that `taken` lacks."""
    n = 0
    while (base if n == 0 else f"{base}{n}") in taken:
        n += 1
    return base if n == 0 else f"{base}{n}"


def rename(text: str, insts: dict[str, str]) -> str:
    """The text with the renames applied; `insts` gives each instance the
    text may read with its present component, and holds only those the
    renames apply to."""
    from arclog_convert.lint import L, Sym, read
    edits: list[tuple[int, int, str]] = []

    def inputs(y, top: bool, parts: dict[str, str]) -> None:
        for it in (y.items[3:] if top else y.items[1:]):
            if isinstance(it, L) and it.head == "key":
                inputs(it, False, parts)
            elif isinstance(it, L) and it.head in parts:
                hs = it.items[0]
                edits.append((hs.pos, hs.pos + len(hs.text), parts[it.head]))

    def walk(x) -> None:
        if not isinstance(x, L):
            return
        h = x.head
        if h == "INIT" and len(x.items) >= 3 and isinstance(x.items[1], Sym) and x.items[1].text in insts:
            r = COMP[insts[x.items[1].text]]
            s = x.items[2]
            edits.append((s.pos, s.pos + len(s.text), r.name))
            inputs(x, True, r.parts)
        if h in ("DET", "DET_OR_RULE", "RULE_OR_DET", "param"):
            for it in x.items[2:]:
                s = it if isinstance(it, Sym) else (
                    it.items[0] if isinstance(it, L) and it.items and isinstance(it.items[0], Sym) else None)
                if s is not None and s.text in DERIVATIONS and DERIVATIONS[s.text] != s.text:
                    edits.append((s.pos, s.pos + len(s.text), DERIVATIONS[s.text]))
        if h in REL:
            r = REL[h]
            parts = [r.name]
            axis: str | None = None
            for it in x.items[1:]:
                if r.guard and isinstance(it, Sym) and it.text.lstrip("*^") == r.guard[0]:
                    axis = it.text
                elif (r.guard and isinstance(it, L) and it.head == f":{r.guard[0]}"
                      and len(it.items) == 2 and isinstance(it.items[1], Sym)):
                    axis = it.items[1].text
                if isinstance(it, Sym):
                    col = it.text.lstrip("*^")
                    parts.append(site_text(r.parts.get(col, col), it.text) if col != "0" else it.text)
                elif isinstance(it, L) and it.head and it.head.startswith(":"):
                    col = it.head[1:]
                    lab = text[it.items[1].pos if isinstance(it.items[1], Sym) else it.items[1].start:it.end - 1]
                    parts.append(site_text(r.parts.get(col, col), lab)
                                 if isinstance(it.items[1], Sym) and len(it.items) == 2
                                 else f"(:{r.parts.get(col, col)} {lab})")
                else:
                    parts.append(text[it.start:it.end])
            guard = ""
            if r.guard and len(x.items) > 1:
                src, rel, gcol = r.guard
                col = r.parts.get(src, src)
                if axis is None:
                    axis = "*" + fresh(col, taken)
                    taken.add(axis[1:])
                    parts.insert(1, site_text(col, axis))
                if axis[0] in "*^":
                    guard = f" ({rel} {site_text(gcol, axis[1:])})"
            edits.append((x.start, x.end, "(" + " ".join(parts) + ")" + guard))
            return
        for it in x.items:
            if isinstance(it, Sym):
                m = READ.match(it.text)
                if m and m[2] in insts:
                    new = COMP[insts[m[2]]].parts.get(m[3])
                    if new is not None:
                        edits.append((it.pos, it.pos + len(it.text), f"{m[1] or ''}{m[2]}.{new}{m[4]}"))
            walk(it)

    for f in read(text):
        taken = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", text[f.start:f.end])) if isinstance(f, L) else set()
        walk(f)
    edits.sort(key=lambda e: -e[0])
    bound = 10 ** 12
    for s, e, new in edits:
        if e > bound:
            continue   # inside an atom already rewritten
        text = text[:s] + new + text[e:]
        bound = s
    return text
