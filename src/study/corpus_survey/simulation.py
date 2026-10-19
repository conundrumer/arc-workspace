"""A body of `gen/` evaluated in sqlite over the Souffle rows of its
solver on one input (`solver_runs.dump`): its stored atoms as tables of the
rows of the case its alts pin, its algebra atoms as the templates of
`algebra.SPEC`, and the count of the bindings of a set of its items, which
the Prefix sizes and Join orders sections read."""

import json
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from arclog_convert.lint import LIB
from study.corpus_survey import algebra
from study.corpus_survey.bodies import (
    CLAUSES,
    Body,
    Item,
    Kind,
    flat,
    is_const,
    item_kind,
    key_labels,
    site_pairs,
    stored,
    strip,
)
from study.corpus_survey.trees import Node, head, is_sym, nodes

OVER = 100_000_000
"""The count past which a count is `over`."""
MEASURED = frozenset({Kind.RULE, Kind.DET_OR_RULE, Kind.RULE_OR_DET, Kind.INPUT, Kind.KEY})
"""The kinds of the bodies the simulation measures: no `DET` body, whose
relation the solver stores."""
CMP = frozenset({"<", "<=", ">", ">=", "!="})

class Mark(StrEnum):
    """A count that gave no number."""
    OVER = "over"
    TIMEOUT = "timeout"


type Count = int | Mark


class Entry(StrEnum):
    """The kind of an item of a body as the simulation applies it."""
    STORED = "S"
    ALGEBRA = "ALG"
    EQUAL = "EQ"
    COMPARE = "CMP"


class Status(StrEnum):
    """What the measure of a body gave."""
    OK = "ok"
    UNRESOLVED = "unresolved"
    NO_STORED = "no stored atom"
    FAILED = "failed"
    NO_RUN = "no run"
    NO_ROWS = "no rows"
    TIMEOUT = "timeout"
    NO_ORDER = "no order"


def measured(b: Body) -> bool:
    return b.kind in MEASURED and (b.kind in CLAUSES or b.form == "INIT")


@dataclass
class Stem:
    """One solver's arclog tree, its `ALTS` groups, its instances' key
    labels, and its dump."""
    stem: str
    tree: list[Node]
    dump: dict[str, Any]
    constructors: dict[str, str]
    """Each arclog `ALT` name with its Souffle constructor."""
    groups: list[tuple[str, str | None, set[str]]] = field(default_factory=list)
    ikeys: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for n in (x for f in self.tree for x in nodes(f)):
            if head(n) == "ALTS":
                default = str(n[3]) if len(n) > 3 and is_sym(n[3]) else None
                ctors = {default} if default else set()
                ctors |= {str(y[1]) for y in n[4:] if head(y) == "ALT"}
                self.groups.append((str(n[1]), default, ctors))
            elif head(n) == "INIT" and len(n) > 2:
                ks: list[str] | None = None
                for y in n[3:]:
                    if head(y) == "key":
                        assert isinstance(y, list)
                        ks = list(key_labels(y[1]))
                self.ikeys.setdefault(str(n[1]), ks if ks is not None else [])
        self.allctor = {self.souffle(c) for _, _, cs in self.groups for c in cs}

    def souffle(self, alt: str) -> str:
        """The constructor of an arclog `ALT` name as a dumped row holds it."""
        return "$" + self.constructors[alt]

    def pins(self, b: Body) -> frozenset[str]:
        """The constructors the case of `b` takes: each group's concept alt,
        else the alt `b` stands in."""
        chosen = {name: default for name, default, _ in self.groups}
        for f in b.stack:
            if f.head == "ALT":
                for name, _, ctors in self.groups:
                    if f.name in ctors:
                        chosen[name] = f.name
        return frozenset(self.souffle(v) for v in chosen.values() if v)


def canon(v: Any) -> Any:
    return v if isinstance(v, int) else json.dumps(v, separators=(",", ":"))


def is_adt(v: Any) -> bool:
    return isinstance(v, str) and v.startswith("$")


def leaves(v: Any):
    if isinstance(v, list):
        for x in v:
            yield from leaves(x)
    elif is_adt(v):
        yield v


class Eval:
    """The sqlite database of one stem on one input."""

    def __init__(self, st: Stem, idx: str, limit: float):
        self.st, self.idx, self.limit = st, idx, limit
        self.inp = st.dump["inputs"][idx]
        self.con = sqlite3.connect(":memory:")
        self.con.execute("pragma temp_store=memory")
        self.tabs: dict[tuple[str, frozenset[str], int], tuple[str, dict[str, str], set[str], int] | None] = {}
        self.deadline: float | None = None
        self.con.set_progress_handler(self.progress, 200000)
        for name, (k, f) in algebra.FUNCTIONS.items():
            self.con.create_function(name, k, guarded(f), deterministic=True)
        self.otab: dict[str, list[str]] = {}
        for rel, rows in algebra.tables().items():
            cols = [c for c, _ in LIB.top[rel]] if rel in LIB.top else [f"c{i}" for i in range(len(rows[0]))]
            n = len(rows[0]) if rows else len(cols)
            self.con.execute("create table o_%s (%s)" % (rel, ",".join("c%d" % i for i in range(n))))
            self.con.executemany("insert into o_%s values (%s)" % (rel, ",".join("?" * n)), rows)
            self.otab[rel] = cols
        for dn, vals in algebra.DOMAINS.items():
            self.con.execute("create table dom_%s (v)" % dn)
            self.con.executemany("insert into dom_%s values (?)" % dn, [(v,) for v in vals])

    def progress(self) -> int:
        return 1 if self.deadline and time.time() > self.deadline else 0

    def count(self, sql: str) -> Count:
        self.deadline = time.time() + self.limit
        try:
            n = self.con.execute(sql).fetchone()[0]
        except sqlite3.OperationalError as e:
            if "interrupt" in str(e):
                return Mark.TIMEOUT
            raise
        finally:
            self.deadline = None
        return Mark.OVER if n > OVER else n

    def table(self, name: str, pins: frozenset[str], k: int):
        """The table of the dumped relation `name` at the case `pins`
        takes, with its key split into `k` fields: its name, its columns,
        its numeric columns and its rows; None where it cannot be built."""
        key = (name, pins, k)
        if key in self.tabs:
            return self.tabs[key]
        rel = self.inp["rel"].get(name)
        cols = self.st.dump["cols"].get(name)
        if rel is None or cols is None or rel.get("over"):
            self.tabs[key] = None
            return None
        keyi = next((j for j, (cn, _) in enumerate(cols) if cn == "key"), None)
        rows: set[tuple[Any, ...]] = set()
        for r in rel["rows"]:
            if any(lf in self.st.allctor and lf not in pins for v in r for lf in leaves(v)):
                continue
            row: list[Any] = []
            for j, v in enumerate(r):
                if j != keyi:
                    row.append(canon(v))
                    continue
                if is_adt(v):
                    fields_, sa = [], True
                elif isinstance(v, list):
                    fields_ = [x for x in v if not is_adt(x)]
                    sa = len(fields_) != len(v)
                else:
                    fields_, sa = [v], False
                kf = fields_ if k == len(fields_) else [v if not sa else fields_] if k == 1 else None
                if kf is None:
                    self.tabs[key] = None
                    return None
                row.extend(canon(x) for x in kf)
            rows.add(tuple(row))
        names: list[str] = []
        for j, (cn, _) in enumerate(cols):
            names += [f"key.{i}" for i in range(k)] if j == keyi else [cn.lower()]
        tn = f"t{len(self.tabs)}"
        sc = [f"c{i}" for i in range(len(names))]
        self.con.execute(f"create table {tn} ({','.join(sc)})")
        if rows:
            self.con.executemany(f"insert into {tn} values ({','.join('?' * len(sc))})", list(rows))
        numeric = {f"c{i}" for i in range(len(names)) if rows and all(isinstance(x[i], int) for x in rows)}
        got = (tn, {n: f"c{i}" for i, n in enumerate(names)}, numeric, len(rows))
        self.tabs[key] = got
        return got

    def close(self) -> None:
        self.con.close()


def guarded(f):
    def g(*a):
        try:
            return f(*a)
        except Exception:
            return None
    return g


def resolve_atom(it: list[Node], ev: Eval, pins: frozenset[str], st: Stem) -> tuple[dict[str, Any] | None, str | None]:
    """The table of a stored atom, with the sqlite column of each of its
    sites; None and why where it has none."""
    rel = str(it[0])
    name = "in" if rel == "input" else rel[1:]
    if rel in ("ex_input", "ex_output"):
        return None, "fact:" + rel
    if name not in st.dump["alias"]:
        return None, "unres:" + name
    inst = name.split(".")[0] if "." in name else None
    klabels = st.ikeys.get("&" + inst, []) if inst else []
    cols = st.dump["cols"].get(name)
    if cols is None:
        return None, "nocols:" + name
    haskey = any(c[0] == "key" for c in cols)
    kk = len(klabels) if haskey else 0
    tb = ev.table(name, pins, kk)
    if tb is None:
        return None, "notable:" + name
    tn, cmap, numeric, nrows = tb
    sites: list[tuple[str, str]] = []
    for s in it[1:]:
        for path, tok in site_pairs(s):
            segs = path.split(".")
            c = segs[0].lower()
            if c == "key" and haskey:
                if len(segs) == 1:
                    if kk != 1:
                        return None, "keywhole:" + name
                    sites.append((cmap["key.0"], tok))
                else:
                    idx = [i for i, lab in enumerate(klabels) if lab.lower() == segs[1].lower()]
                    if not idx or len(segs) > 2:
                        return None, "keyfield:" + name + "." + path
                    sites.append((cmap[f"key.{idx[0]}"], tok))
            else:
                if len(segs) > 1:
                    return None, "subfield:" + name + "." + path
                if c not in cmap:
                    return None, "nocol:" + name + "." + c
                sites.append((cmap[c], tok))
    return dict(rel=rel, tn=tn, sites=sites, numeric=numeric, n=nrows), None


def is_num(tok: str) -> bool:
    return strip(tok).lstrip("-").isdigit()


class Query:
    """The FROM and WHERE parts of a count, and the sqlite expression of
    each label bound so far."""

    def __init__(self, ev: Eval):
        self.ev = ev
        self.froms: list[str] = []
        self.where: list[str] = []
        self.col: dict[str, str] = {}
        self.n = 0

    def alias(self) -> str:
        self.n += 1
        return "a%d" % self.n

    def expr(self, tok: str) -> str | None:
        if is_const(tok):
            t = strip(tok)
            return t if t.lstrip("-").isdigit() else None
        return self.col.get(strip(tok))

    def bind(self, tok: str, e: str) -> None:
        if is_const(tok):
            if e is not None and is_num(tok):
                self.where.append("(%s)=%s" % (e, strip(tok)))
            return
        lab = strip(tok)
        if lab in self.col:
            self.where.append("(%s)=(%s)" % (self.col[lab], e))
        else:
            self.col[lab] = e

    def stored(self, a: dict[str, Any]) -> None:
        al = self.alias()
        used: dict[str, list[str]] = {}
        conds: list[str] = []
        for sc, tok in a["sites"]:
            if is_const(tok):
                if is_num(tok):
                    conds.append("%s=%d" % (sc, int(strip(tok))))
                continue
            used.setdefault(sc, []).append(tok)
        if a["n"] == 0:
            self.where.append("0")
            return
        if not used:
            if conds:
                self.froms.append("(SELECT 1 AS one FROM %s WHERE %s LIMIT 1) %s" % (a["tn"], " AND ".join(conds), al))
            return
        self.froms.append("(SELECT DISTINCT %s FROM %s%s) %s" % (",".join(used), a["tn"], " WHERE " + " AND ".join(conds) if conds else "", al))
        for sc, toks in used.items():
            for tok in toks:
                self.bind(tok, "%s.%s" % (al, sc))

    def table_atom(self, rel: str, toks: list[tuple[str, str]]) -> bool:
        cols = self.ev.otab[rel]
        sites = []
        for c, tok in toks:
            if c not in cols:
                return False
            sites.append(("c%d" % cols.index(c), tok))
        self.stored({"tn": "o_" + rel, "sites": sites, "n": 1})
        return True

    def try_alg(self, rel: str, toks: list[tuple[str, str]], allow_enum: bool, negate: bool = False) -> str:
        """`done`, `blocked` or `skip`: whether the algebra atom applied."""
        if rel in self.ev.otab:
            if negate:
                return "skip"
            return "done" if self.table_atom(rel, toks) else "skip"
        sp = algebra.SPEC.get(rel)
        if sp is None:
            return "skip"
        d: dict[str, str] = {}
        for c, tok in toks:
            d.setdefault(c, tok)
        enum = sp.get("enum", {})
        if any(is_const(tok) and not is_num(tok) for tok in d.values()):
            return "skip"
        ex = {c: self.expr(t) for c, t in d.items()}
        hidden = [c for c in enum if c not in d]
        free = [c for c in enum if c in d and ex[c] is None]
        if (free or hidden) and not allow_enum:
            return "blocked"
        ex2 = dict(ex)
        pre_from: list[str] = []
        for c in free + hidden:
            if (c in hidden and "check" in sp) or negate:
                ex2[c] = "ev_%s.v" % c
            else:
                al = self.alias()
                pre_from.append("dom_%s %s" % (enum[c], al))
                ex2[c] = "%s.v" % al
        if "check" in sp:
            exist = [c for c in free + hidden if (c in hidden or negate)]
            need = re.findall(r"\{(\w+)\}", sp["check"])
            if any(ex2.get(c) is None for c in need):
                return "blocked"
            cond = sp["check"].format(**{c: ex2[c] for c in need})
            if exist:
                cond = "EXISTS (SELECT 1 FROM %s WHERE %s)" % (", ".join("dom_%s ev_%s" % (enum[c], c) for c in exist), cond)
            self.froms += pre_from
            for c in free:
                if c in d and (ex2[c] or "").startswith("a"):
                    self.bind(d[c], ex2[c] or "")
            self.where.append("NOT (%s)" % cond if negate else cond)
            return "done"
        if negate:
            return "skip"
        for outs, needs in sp["modes"]:
            if all(ex2.get(n) is not None for n in needs):
                self.froms += pre_from
                for c in free:
                    if c in d:
                        self.bind(d[c], ex2[c] or "")
                for oc, tmpl in outs.items():
                    e = tmpl.format(**{k: v for k, v in ex2.items() if v is not None})
                    if oc in d:
                        self.bind(d[oc], e)
                return "done"
        return "blocked"

    def apply(self, pend: list[tuple[Any, ...]], skipped: list[str]) -> None:
        """Applies the algebra atoms and constraints of `pend` as their
        labels are bound, an enumeration allowed where none applies else."""
        allow = False
        while pend:
            nxt = []
            prog = False
            for e in pend:
                if e[0] == Entry.ALGEBRA:
                    r = self.try_alg(e[2], e[3], allow)
                    if r == "done":
                        prog = True
                    elif r == "skip":
                        skipped.append(e[2])
                    else:
                        nxt.append(e)
                elif e[0] == Entry.EQUAL:
                    a, b = e[1], e[2]
                    ea, eb = self.expr(a), self.expr(b)
                    if ea is not None and eb is not None:
                        self.where.append("(%s)=(%s)" % (ea, eb))
                        prog = True
                    elif ea is not None and not is_const(b):
                        self.col[strip(b)] = ea
                        prog = True
                    elif eb is not None and not is_const(a):
                        self.col[strip(a)] = eb
                        prog = True
                    else:
                        nxt.append(e)
                else:
                    op, a, b = e[1], e[2], e[3]
                    ea, eb = self.expr(a), self.expr(b)
                    if ea is not None and eb is not None:
                        self.where.append("(%s)%s(%s)" % (ea, op, eb))
                        prog = True
                    else:
                        nxt.append(e)
            pend = nxt
            if not prog:
                if allow:
                    skipped += [(x[2] if x[0] == Entry.ALGEBRA else str(x[0])) for x in pend]
                    break
                allow = True

    def sql(self, select: str = "1", limit: int = OVER + 1) -> str:
        return ("SELECT COUNT(*) FROM (SELECT %s FROM " % select + (", ".join(self.froms) if self.froms else "(SELECT 1)")
                + (" WHERE " + " AND ".join(self.where) if self.where else "") + " LIMIT %d)" % limit)


def build(ev: Eval, ent: list[tuple[Any, ...]], idx: list[int], negs=(), neg_alg=()) -> tuple[str, list[str]]:
    """The count of the bindings of the entries `idx` of `ent`, with the
    negated atoms `negs` and `neg_alg`; and the algebra atoms it could not
    apply."""
    q = Query(ev)
    inc = [ent[i] for i in idx]
    for e in inc:
        if e[0] == Entry.STORED:
            q.stored(e[1])
    skipped: list[str] = []
    q.apply([e for e in inc if e[0] in (Entry.ALGEBRA, Entry.EQUAL, Entry.COMPARE)], skipped)
    for a in negs:
        conds = []
        for sc, tok in a["sites"]:
            if is_const(tok):
                if is_num(tok):
                    conds.append("n.%s=%d" % (sc, int(strip(tok))))
                continue
            e = q.expr(tok)
            if e is not None:
                conds.append("n.%s=%s" % (sc, e))
        q.where.append("NOT EXISTS (SELECT 1 FROM %s n WHERE %s)" % (a["tn"], " AND ".join(conds) if conds else "1"))
    for rel, toks in neg_alg:
        if q.try_alg(rel, toks, True, negate=True) != "done":
            skipped.append("NOT " + rel)
    return q.sql(), skipped


def sites_of(it: list[Node]) -> list[tuple[str, str]]:
    return [(path.split(".")[0].lower(), t) for s in it[1:] for path, t in site_pairs(s)]


@dataclass
class Classified:
    """A body's top-level items as entries: `S` a stored atom, `ALG` an
    algebra atom or a table, `EQ` an equality, `CMP` a comparison; its
    negated stored and algebra atoms; the forms it does not apply; and the
    atoms it could not resolve."""
    ent: list[tuple[Any, ...]]
    negs: list[dict[str, Any]]
    neg_alg: list[tuple[str, list[tuple[str, str]]]]
    ignored: Counter[str]
    unresolved: list[str]


def classify(items: list[Node], ev: Eval, pins: frozenset[str], st: Stem) -> Classified:
    c = Classified([], [], [], Counter(), [])
    for it in items:
        if not isinstance(it, list) or not it:
            continue
        k = item_kind(it)
        if k == Item.ATOM:
            rel = str(it[0])
            if stored(rel):
                a, why = resolve_atom(it, ev, pins, st)
                if a is None:
                    c.unresolved.append(why or "")
                else:
                    c.ent.append((Entry.STORED, a, it))
            else:
                c.ent.append((Entry.ALGEBRA, it, rel, sites_of(it)))
        elif k == Item.OP:
            labs = flat(it[1:])
            if it[0] == "=" and len(labs) == 2:
                c.ent.append((Entry.EQUAL, labs[0], labs[1], it))
            elif it[0] in CMP and len(labs) == 2:
                c.ent.append((Entry.COMPARE, str(it[0]), labs[0], labs[1], it))
            else:
                c.ignored["op"] += 1
        elif k == Item.NOT:
            inner = it[1] if len(it) > 1 else None
            if isinstance(inner, list) and inner and item_kind(inner) == Item.ATOM:
                rel = str(inner[0])
                if rel == "input" or rel.startswith("&"):
                    a, why = resolve_atom(inner, ev, pins, st)
                    if a is None:
                        c.unresolved.append(why or "")
                    else:
                        c.negs.append(a)
                else:
                    c.neg_alg.append((rel, sites_of(inner)))
            else:
                c.ignored["NOT-other"] += 1
        else:
            c.ignored[k.value] += 1
    return c


def text(x: Node) -> str:
    if isinstance(x, list):
        return "(" + " ".join(text(y) for y in x) + ")"
    return str(x)

