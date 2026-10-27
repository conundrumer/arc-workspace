"""The placement of the forms of an arclog file in its claim blocks, `ALT`
blocks and `RIGID` forms (`Placed`, `placements`), and the analysis of its
alternatives over them: the points of the alts, the cases they make, the
forms that restate another block's meaning, and the things (a relation, or the
`OUT` form) that blocks of a case derive with no block that states the
combination."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from arclog_convert.lint_read import L, Sym, flat, walk

CLAIMS = {"INPUT", "OUTPUT"}
OUT = "OUT"
DECL_HEADS = {"RULE", "DET", "INIT", "CHOOSE", "RIGID_DET", "RIGID", "DEMONSTRATED", "DET_OR_RULE", "RULE_OR_DET"}


@dataclass
class Placed:
    """A form with the claim block, the alt path and the RIGID it stands in."""
    form: L
    name: str | None
    slug: str | None
    claim: str | None
    alts: tuple
    rigid: str | None


def placements(forms, slug=None, claim=None, alts=(), rigid=None, out=None) -> list[Placed]:
    out = [] if out is None else out
    for f in forms:
        if not isinstance(f, L):
            continue
        h = f.head
        nm = f.items[1].text if len(f.items) > 1 and isinstance(f.items[1], Sym) else None
        if h in CLAIMS:
            placements(f.items[2:], nm, h, alts, rigid, out)
        elif h == "ALTS":
            placements(f.items[2:], slug, claim, alts, rigid, out)
        elif h == "ALT":
            placements(f.items[2:], None, None, alts + (nm,), rigid, out)
        elif h == "RIGID":
            out.append(Placed(f, nm, slug, claim, alts, rigid))
            placements(f.items[2:], slug, claim, alts, nm, out)
        else:
            out.append(Placed(f, nm if h in DECL_HEADS else None, slug, claim, alts, rigid))
    return out


def reads(f: L, own: str | None = None) -> set[str]:
    """The declared relations a form reads, by base name."""
    out = set()
    for a in walk(f):
        if isinstance(a, L) and a.head and a.head.startswith("&"):
            b = a.head.partition(".")[0]
            if b != own:
                out.add(b)
    return out


def most_specific(blocks: list, alts=lambda block: block) -> list:
    """The blocks of `blocks` whose alts (`alts` of a block) no other block's alts hold with more."""
    return [b for b in blocks if not any(set(alts(b)) < set(alts(c)) for c in blocks)]


def alt_blocks(forms, alts: tuple = ()) -> list[tuple[tuple, L]]:
    """Each `ALT` block of `forms` with its alt path, in the order of the text: the block of an `ALTS` form at the top
    level or in an `ALT` block, and a block nested in an `ALT` block. Two blocks may have one path."""
    out: list[tuple[tuple, L]] = []
    for f in forms:
        if not isinstance(f, L):
            continue
        if f.head == "ALTS":
            out += alt_blocks(f.items[2:], alts)
        elif f.head == "ALT" and len(f.items) > 1 and isinstance(f.items[1], Sym):
            path = alts + (f.items[1].text,)
            out.append((path, f))
            out += alt_blocks(f.items[2:], path)
    return out


def claims_of(forms) -> list[L]:
    return [f for f in forms if isinstance(f, L) and f.head in CLAIMS]


def alts_map(forms) -> dict[str, set[str]]:
    """Each ALTS form's name and the names of the ALT forms under it, nested
    ones included."""
    out: dict[str, set[str]] = {}
    for f in forms:
        for a in walk(f):
            if isinstance(a, L) and a.head == "ALTS" and len(a.items) > 1 and isinstance(a.items[1], Sym):
                out.setdefault(a.items[1].text, set()).update(
                    x.items[1].text for x in walk(a) if isinstance(x, L) and x.head == "ALT"
                    and len(x.items) > 1 and isinstance(x.items[1], Sym))
    return out


def alt_repeats(pl: list[Placed]) -> list[tuple[str, Placed, Placed, tuple]]:
    """The forms that another place of the file states with the same
    meaning, where one statement serves every case that reads them, each
    as (kind, form, the form it repeats, the block that states it once).

    A block's place is its alt path. A case reads a relation from the
    deepest blocks whose alts it holds that derive it. A form's meaning in a
    case is its text and the meaning of each relation it reads in that case;
    a DET reads in its own block's case. Two kinds are redundant:
    - "enclosing": a form that the blocks around its own derive with the
      same meaning;
    - "shared": one form in several alts with the same meaning, where every other
      block of the case derives no relation of its name and every form that
      reads the relation stands in one of those alts, so that one form in
      the block the alts share states it.
    Equal text that reads a relation the alts derive each in its own way,
    or whose shared block derives the relation in another way, is no
    repeat."""
    defs: dict[str, dict[tuple, Placed]] = defaultdict(dict)
    for p in pl:
        if p.name and p.name.startswith("&") and p.rigid is None:
            defs[p.name.partition(".")[0]].setdefault(p.alts, p)
    readers: dict[str, list[Placed]] = defaultdict(list)
    for p in pl:
        for r in reads(p.form, p.name.partition(".")[0] if p.name else None):
            readers[r].append(p)

    def resolve(case: tuple, n: str, skip: tuple | None = None) -> list[tuple]:
        return most_specific([q for q in defs.get(n, {}) if set(q) <= set(case) and q != skip])

    ids: dict = {}
    memo: dict = {}

    def meaning(p: Placed, case: tuple, at: tuple | None = None) -> int:
        if p.form.head == "DET":
            case = p.alts if at is None else at
        key = (id(p), case)
        if key in memo:
            return memo[key] if memo[key] is not None else -1
        memo[key] = None
        own = (p.name or "").partition(".")[0]
        m = (flat(p.form), tuple(sorted(
            (r, frozenset(meaning(defs[r][q], case) for q in resolve(case, r)))
            for r in reads(p.form, own) if r in defs)))
        memo[key] = ids.setdefault(m, len(ids))
        return memo[key]

    out = []
    for n, at in defs.items():
        for path, p in at.items():
            inh = resolve(path, n, skip=path) if path else []
            if inh and all(meaning(at[q], path) == meaning(p, path) for q in inh):
                out.append(("enclosing", p, at[inh[0]], inh[0]))
        if len(at) < 2:
            continue
        texts = {flat(p.form) for p in at.values()}
        if len(texts) != 1:
            continue   # another block derives the relation in another way
        paths = list(at)
        if any(set(a) < set(b) for a in paths for b in paths):
            continue
        shared: tuple = ()
        for i in range(min(map(len, paths))):
            if len({q[i] for q in paths}) != 1:
                break
            shared += (paths[0][i],)
        first = at[paths[0]]
        same = {meaning(p, path) for path, p in at.items()}
        if first.form.head == "DET":
            same.add(meaning(first, shared, shared))   # a DET in the shared block reads in its case
        if len(same) != 1:
            continue
        if not all(any(set(q) <= set(r.alts) for q in paths) for r in readers.get(n, [])):
            continue   # a case that none of the alts holds reads the relation
        for path in paths[1:]:
            out.append(("shared", at[path], first, shared))
    return out


def alt_points(forms) -> tuple[dict[str, str], dict[str, str | None]]:
    """Each alt's point, the ALTS form whose ALT block it is, and each
    point's alt that its ALTS form stands under, or None at the top level."""
    point: dict[str, str] = {}
    under: dict[str, str | None] = {}

    def go(xs, alt: str | None) -> None:
        for f in xs:
            if not isinstance(f, L):
                continue
            nm = f.items[1].text if len(f.items) > 1 and isinstance(f.items[1], Sym) else None
            if f.head == "ALTS" and nm:
                under.setdefault(nm, alt)
                for a in f.items[2:]:
                    if isinstance(a, L) and a.head == "ALT" and len(a.items) > 1 and isinstance(a.items[1], Sym):
                        point.setdefault(a.items[1].text, nm)
                        go(a.items[2:], a.items[1].text)
            elif f.head in CLAIMS:
                go(f.items[2:], alt)
    go(forms, None)
    return point, under


def is_case(c: frozenset, point: dict[str, str], under: dict[str, str | None],
            excluded: tuple[frozenset, ...] | list[frozenset]) -> bool:
    """Whether the alts `c` are a case: one alt for each point, a nested
    point's alt with its parent's (`alt_points` gives `point` and `under`),
    and no combination that `excluded`, the arcdata file's excludes, leaves out."""
    pts = [point[a] for a in c]
    if len(set(pts)) != len(pts):
        return False   # two alts of one point
    return all(under[pt] is None or under[pt] in c for pt in pts) and not any(x <= c for x in excluded)


def derived(p: Placed) -> str | None:
    """The thing that the form `p` derives, for the rule that a case takes the forms of its most specific blocks: a
    relation by its base name, or `OUT` for the `OUT` form; none for any other form."""
    if p.form.head == OUT:
        return OUT
    if p.name and p.name.startswith("&") and p.rigid is None:
        return p.name.partition(".")[0]
    return None


def unstated_combinations(pl: list[Placed], forms, excluded: tuple[frozenset, ...] | list[frozenset] = ()
                          ) -> list[tuple[str, frozenset, list[Placed]]]:
    """The things (`derived`) that a case reads from several blocks, none of which
    holds the others' alts: alts of different points each rederive the
    relation or hold an `OUT` form, and no nested ALT states what their combination derives. A
    combination that `excluded`, the arcdata file's excludes, leaves out is
    no case. Each is (thing, the case, the blocks' first forms)."""
    point, under = alt_points(forms)
    defs: dict[str, dict[frozenset, list[Placed]]] = defaultdict(dict)
    for p in pl:
        if (thing := derived(p)) and p.alts and all(a in point for a in p.alts):
            defs[thing].setdefault(frozenset(p.alts), []).append(p)

    out = []
    for n, at in defs.items():
        if len(at) < 2:
            continue
        cases = {frozenset()}
        for q in at:
            cases |= {c | q for c in cases if is_case(c | q, point, under, excluded)}
        seen: set[frozenset] = set()
        for c in sorted(cases, key=len):
            deep = most_specific([q for q in at if q <= c])
            if len(deep) < 2 or len({tuple(flat(p.form) for p in at[q]) for q in deep}) < 2:
                continue
            key = frozenset(deep)
            if any(k <= key for k in seen):
                continue   # a smaller case with these blocks is reported
            seen.add(key)
            out.append((n, c, [at[q][0] for q in deep]))
    return out


def restated_outs(pl: list[Placed]) -> list[Placed]:
    """The `OUT` forms that restate the `OUT` form their cases take without them: an `OUT` form in a block that holds
    the alts of other blocks that hold an `OUT` form, equal to the `OUT` form of each most specific such block, the
    tail included as the block of no alt."""
    outs = [p for p in pl if p.form.head == OUT]
    found = []
    for p in outs:
        specific = most_specific([q for q in outs if set(q.alts) < set(p.alts)], lambda q: q.alts)
        if specific and all(flat(q.form) == flat(p.form) for q in specific):
            found.append(p)
    return found
