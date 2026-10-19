"""The Join orders section: the variable order of
`docs/engine/evaluator.md#joins` simulated on the bodies of Join shapes
that join on a computed key or are cyclic through stored relations, over
the rows of Prefix sizes, against the written order and the best order.

The count of a set of variables is the number of its bindings that agree
with each atom projected onto the set. The work of an order is the sum,
over its variables, of the fewest extensions that one atom gives the
bindings so far, plus the rows of each computed-key index the order
builds."""

import time
from collections import Counter
from enum import StrEnum
from multiprocessing import Pool
from typing import Any

from controlled_markdown import mctx
from study.corpus_survey import algebra, kept
from study.corpus_survey.bodies import CLAUSES, Kind, is_const, strip
from study.corpus_survey.corpus import bodies_of, corpus
from study.corpus_survey.joins import computed_keys, join
from study.corpus_survey.prefix import WORKERS, stem_of
from study.corpus_survey.section import Section, body, items, ran, table
from study.corpus_survey.simulation import OVER, Entry, Eval, Mark, Query, Status, classify, text

MAXDP = 9
"""The most variables of a body whose best order is searched."""
BIG = OVER + 1
LIMIT = 6.0
BODY_LIMIT = 60.0
"""The seconds the counts of one body may take."""
COMPUTED, CYCLIC = "computed key", "cyclic"


class Timeout(Exception):
    pass


class Role(StrEnum):
    """What an item of a simulated body does: a table it joins, a function
    that binds its outputs from the inputs of a mode, a check."""
    TABLE = "table"
    FUNCTION = "function"
    CHECK = "check"


def targets(name: str) -> dict[int, set[str]]:
    """The bodies of `name` the section simulates, by index, with the
    groups each is in."""
    found: dict[int, set[str]] = {}
    for bi, b in enumerate(bodies_of(corpus(), name)):
        if b.kind not in CLAUSES and b.kind != Kind.INPUT:
            continue
        groups = set()
        if computed_keys(b):
            groups.add(COMPUTED)
        if join(b.items).stored_cyclic:
            groups.add(CYCLIC)
        if groups:
            found[bi] = groups
    return found


def labs(toks: list[str]) -> set[str]:
    return {strip(t) for t in toks if not is_const(t)}


def prep(ent: list[tuple[Any, ...]], ev: Eval) -> list[dict[str, Any]]:
    """The entries as items: `S` a table, `F` a function by its modes, `C`
    a check."""
    out: list[dict[str, Any]] = []
    for e in ent:
        if e[0] == Entry.STORED:
            out.append(dict(k=Role.TABLE, a=e[1], L=labs([t for _, t in e[1]["sites"]]), n=e[1]["n"], text=text(e[2])))
        elif e[0] == Entry.ALGEBRA:
            rel, toks = e[2], e[3]
            if rel in ev.otab:
                cols = ev.otab[rel]
                if any(c not in cols for c, _ in toks):
                    continue
                sites = [("c%d" % cols.index(c), t) for c, t in toks]
                n = ev.con.execute("select count(*) from o_%s" % rel).fetchone()[0]
                out.append(dict(k=Role.TABLE, a={"tn": "o_" + rel, "sites": sites, "n": n}, L=labs([t for _, t in sites]), n=n, text=rel))
                continue
            sp = algebra.SPEC.get(rel)
            if sp is None:
                continue
            d: dict[str, list[str]] = {}
            for c, t in toks:
                d.setdefault(c, []).append(t)
            enum = sp.get("enum", {})
            dom = {strip(t): len(algebra.DOMAINS[dn]) for c, dn in enum.items() for t in d.get(c, []) if not is_const(t)}
            modes = []
            for outs, needs in sp.get("modes", []):
                ins = labs([t for c in needs for t in d.get(c, [])]) | labs([t for c in enum if c not in needs for t in d.get(c, [])])
                modes.append((ins, labs([t for c in outs for t in d.get(c, [])]) - ins))
            out.append(dict(k=Role.FUNCTION if modes else Role.CHECK, e=e, rel=rel, L=labs([t for _, t in toks]), dom=dom, modes=modes, text=rel))
        elif e[0] == Entry.EQUAL:
            a, b = strip(e[1]), strip(e[2])
            L = labs([e[1], e[2]])
            modes = [({a}, {b}), ({b}, {a})] if len(L) == 2 else []
            out.append(dict(k=Role.FUNCTION if modes else Role.CHECK, e=e, L=L, dom={}, modes=modes, text="="))
        else:
            out.append(dict(k=Role.CHECK, e=e, L=labs([e[2], e[3]]), dom={}, modes=[], text=e[1]))
    return out


def count_sql(ev: Eval, parts: list[tuple[str, Any]], S: set[str]) -> tuple[str, list[str]]:
    q = Query(ev)
    for k, x in parts:
        if k == Role.TABLE:
            q.stored(x)
    q.apply([x for k, x in parts if k != Role.TABLE], [])
    cols = [q.col[v] for v in sorted(S) if v in q.col]
    missing = [v for v in S if v not in q.col]
    if cols:
        return q.sql("DISTINCT " + ",".join("(%s)" % c for c in cols)), missing
    return q.sql("1", 1), missing


class Simulated:
    """One body's items on one input, and its counts so far."""

    def __init__(self, ev: Eval, its: list[dict[str, Any]], keycols: tuple[str, ...], deadline: float):
        self.ev, self.items, self.key, self.deadline = ev, its, set(keycols), deadline
        self.cache: dict[tuple[str, tuple[str, ...]], int] = {}
        self.V: list[str] = []
        for it in its:
            for v in sorted(it["L"]):
                if v not in self.V and v not in self.key:
                    self.V.append(v)
        self.dom: dict[str, int] = {}
        for it in its:
            for v, n in it.get("dom", {}).items():
                self.dom[v] = min(self.dom.get(v, n), n)

    def restricted(self, it: dict[str, Any], S: set[str]) -> dict[str, Any]:
        return dict(it["a"], sites=[(c, t) for c, t in it["a"]["sites"] if is_const(t) or strip(t) in S])

    def filt(self, S0) -> list[tuple[str, Any]]:
        S = set(S0) | self.key
        parts: list[tuple[str, Any]] = []
        for it in self.items:
            if it["k"] == Role.TABLE:
                parts.append((Role.TABLE, self.restricted(it, S)))
            elif (it["k"] == Role.CHECK and it["L"] - set(it["dom"]) <= S) or \
                    (it["k"] == Role.FUNCTION and (any(ins <= S and (ous & S) for ins, ous in it["modes"]) or it["L"] <= S)):
                e = it["e"]
                if e[0] == Entry.ALGEBRA:
                    e = (e[0], e[1], e[2], [(c, t) for c, t in e[3] if is_const(t) or strip(t) in S])
                parts.append((Role.CHECK, e))
        return parts

    def count(self, parts: list[tuple[str, Any]], S) -> int:
        if time.time() > self.deadline:
            raise Timeout()
        sql, missing = count_sql(self.ev, parts, set(S) | self.key)
        k = (sql, tuple(sorted(missing)))
        if k not in self.cache:
            r = self.ev.count(sql)
            n = BIG if isinstance(r, Mark) else r
            for v in missing:
                n *= self.dom.get(v, 1)
            self.cache[k] = n
        return self.cache[k]

    def bindings(self, S) -> int:
        return self.count(self.filt(S), S)

    def placeable(self, v: str, S0) -> bool:
        S = set(S0) | self.key
        for it in self.items:
            if v not in it["L"]:
                continue
            if it["k"] == Role.TABLE or v in it.get("dom", {}):
                return True
            if any(v in ous and ins <= S for ins, ous in it.get("modes", [])):
                return True
        return False

    def W(self, S0, v: str, index: bool):
        S = set(S0)
        S1 = S | {v}
        base = self.filt(S)
        opts: list[tuple[int, tuple[Any, ...] | None]] = []
        for it in self.items:
            if v not in it["L"]:
                continue
            if it["k"] == Role.TABLE:
                opts.append((self.count(base + [(Role.TABLE, self.restricted(it, S1 | self.key))], S1), None))
            if v in it.get("dom", {}):
                opts.append((self.bindings(S) * it["dom"][v], None))
            for ins, ous in it.get("modes", []):
                if v in ous and ins <= S | self.key:
                    opts.append((self.count(self.filt(S1), S1), None))
        if index:
            for f in self.items:
                if f["k"] != Role.FUNCTION or v not in f["L"]:
                    continue
                for ins, ous in f["modes"]:
                    if v in ins and ous and ous <= S | self.key and ins <= S1 | self.key:
                        for it in self.items:
                            if it["k"] == Role.TABLE and v in it["L"]:
                                parts = base + [(Role.TABLE, self.restricted(it, S1 | self.key)), (Role.CHECK, f["e"])]
                                opts.append((self.count(parts, S1), ("ix", it["text"], f.get("rel", "="), it["n"])))
        return min(opts, key=lambda o: o[0]) if opts else None

    def run_order(self, order: list[str] | None, index: bool) -> dict[str, Any] | None:
        if order is None:
            return None
        S: list[str] = []
        maxi = work = 0
        built: set[tuple[Any, ...]] = set()
        for v in order:
            w = self.W(S, v, index)
            if w is None:
                return None
            n, how = w
            if how and how not in built:
                built.add(how)
                work += how[3]
            work += n
            S.append(v)
            maxi = max(maxi, self.bindings(S))
        return dict(order=order, maxi=maxi, work=work)

    def emit(self, key) -> list[str] | None:
        rest = sorted(self.V, key=key)
        out: list[str] = []
        while rest:
            v = next((v for v in rest if self.placeable(v, out)), None)
            if v is None:
                return None
            out.append(v)
            rest.remove(v)
        return out

    def first(self) -> dict[str, int]:
        pos: dict[str, int] = {}
        for i, it in enumerate(self.items):
            for v in it["L"]:
                pos.setdefault(v, i)
        return pos

    def rank(self, v: str) -> float:
        sz = [it["n"] for it in self.items if it["k"] == Role.TABLE and v in it["L"]]
        if v in self.dom:
            sz.append(self.dom[v])
        return min(sz) if sz else float("inf")

    def rule(self) -> list[str] | None:
        """The rule's order: each function output directly once a mode's
        inputs are bound, else the variable of the smallest relation, ties
        by the written order."""
        pos = self.first()
        out: list[str] = []
        rest = list(self.V)
        while rest:
            fo = [v for v in rest if self.rank(v) == float("inf") and self.placeable(v, out)]
            if fo:
                v = min(fo, key=lambda v: pos[v])
            else:
                cands = [v for v in rest if self.placeable(v, out)]
                if not cands:
                    return None
                v = min(cands, key=lambda v: (self.rank(v), pos[v]))
            out.append(v)
            rest.remove(v)
        return out

    def best(self, index: bool) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        V, n = self.V, len(self.V)
        if n > MAXDP:
            return None, None
        inf = float("inf")
        g: dict[int, tuple[float, int | None]] = {0: (0, None)}
        h: dict[int, tuple[float, int | None]] = {0: (0, None)}
        for mask in sorted(range(1, 1 << n), key=lambda m: bin(m).count("1")):
            S = [V[i] for i in range(n) if mask >> i & 1]
            bg: tuple[float, int | None] = (inf, None)
            bh: tuple[float, int | None] = (inf, None)
            iS = None
            for i in range(n):
                if not mask >> i & 1:
                    continue
                pm = mask ^ (1 << i)
                P = [V[j] for j in range(n) if pm >> j & 1]
                if g.get(pm, (inf,))[0] == inf and h.get(pm, (inf,))[0] == inf:
                    continue
                if not self.placeable(V[i], P):
                    continue
                if iS is None:
                    iS = self.bindings(S)
                if g[pm][0] < inf:
                    x = max(g[pm][0], iS)
                    if x < bg[0]:
                        bg = (x, i)
                if h[pm][0] < inf:
                    w = self.W(P, V[i], index)
                    if w is not None:
                        x = h[pm][0] + w[0] + (w[1][3] if w[1] else 0)
                        if x < bh[0]:
                            bh = (x, i)
            g[mask], h[mask] = bg, bh
        full = (1 << n) - 1
        return (dict(maxi=g[full][0]) if g[full][0] < inf else None,
                dict(work=h[full][0]) if h[full][0] < inf else None)


def simulate_stem(name: str) -> list[dict[str, Any]]:
    tg = targets(name)
    if not tg:
        return []
    try:
        st = stem_of(name)
    except Exception as e:  # a solver that does not load or run
        return [dict(stem=name, status=Status.NO_ROWS, err=repr(e)[:200], groups=sorted(g)) for g in tg.values()]
    bs = bodies_of(corpus(), name)
    res: list[dict[str, Any]] = []
    for bi, groups in tg.items():
        b = bs[bi]
        for idx, inp in st.dump["inputs"].items():
            if "rel" not in inp:
                continue
            r: dict[str, Any] = dict(stem=name, kind=b.kind.value, name=b.name, bi=bi, input=idx, groups=sorted(groups))
            ev = Eval(st, idx, LIMIT)
            try:
                c = classify(b.items, ev, st.pins(b), st)
                if c.unresolved:
                    r.update(status=Status.UNRESOLVED, why=c.unresolved[:3])
                    res.append(r)
                    continue
                sim = Simulated(ev, prep(c.ent, ev), b.keycols, time.time() + BODY_LIMIT)
                pos = sim.first()
                written, rule = sim.emit(lambda v: pos[v]), sim.rule()
                r.update(nvars=len(sim.V), written=sim.run_order(written, True), rule=sim.run_order(rule, True),
                         rule_noix=sim.run_order(rule, False), status=Status.OK)
                sim.deadline = time.time() + BODY_LIMIT
                try:
                    r["best_max"], r["best_work"] = sim.best(True)
                except Timeout:
                    r["best_max"] = r["best_work"] = None
            except Timeout:
                r["status"] = Status.TIMEOUT
            except Exception as e:  # a body the simulation does not parse
                r.update(status=Status.FAILED, err=repr(e)[:300])
            finally:
                ev.close()
            res.append(r)
    return res


def kept_simulation(name: str) -> list[dict[str, Any]]:
    c = corpus()
    return kept.kept("join-orders", kept.solver_key(name, [c.gen / f"{name}.arclog"]), lambda: simulate_stem(name))


def capped(r: dict[str, Any]) -> bool:
    """Whether a count of the simulation of `r` gave no number."""
    return any(r.get(nm) and (r[nm]["maxi"] >= BIG or r[nm]["work"] >= BIG) for nm in ("written", "rule", "rule_noix"))


def join_orders() -> str:
    with Pool(WORKERS) as p:
        results = [r for rs in p.imap(kept_simulation, corpus().stems, chunksize=1) for r in rs]
    per: dict[tuple[str, int], dict[str, Any]] = {}
    for r in results:
        k = (r["stem"], r.get("bi", -1))
        ok = r.get("status") == Status.OK and all(r.get(x) for x in ("written", "rule"))
        if not ok:
            per.setdefault(k, dict(r, status=r.get("status") if r.get("status") != Status.OK else Status.NO_ORDER))
        elif k not in per or per[k].get("status") != Status.OK or r["written"]["maxi"] > per[k]["written"]["maxi"]:
            per[k] = r
    rows: list[tuple[object, ...]] = []
    notes: list[str] = []
    for grp in (COMPUTED, CYCLIC):
        B = [r for r in per.values() if grp in r.get("groups", [])]
        measured = [r for r in B if r.get("status") == Status.OK]
        ok = [r for r in measured if not capped(r)]
        if len(ok) < len(measured):
            notes.append(mctx("{grp}: {n} bodies reach a count past {big} rows or {limit} s under some order, and stand outside the table: {some}.")
                         .format(grp=grp, n=len(measured) - len(ok), big=OVER, limit=LIMIT,
                                 some=", ".join(f"{r['stem']} `{r['name']}`" for r in measured if capped(r))))
        if not ok:
            rows.append((f"{grp}, 0 of {len(B)}", "", "", ""))
            continue

        def cell(rs: list[dict[str, Any]], nm: str, f: str) -> str:
            xs = [r[nm][f] for r in rs if r.get(nm)]
            return f"{max(xs)} / {sum(xs)}" if xs else ""

        rows.append((f"{grp}, {len(ok)} of {len(B)}", "written", cell(ok, "written", "maxi"), cell(ok, "written", "work")))
        rows.append(("", "the rule", cell(ok, "rule", "maxi"), cell(ok, "rule", "work")))
        rows.append(("", "the rule with no computed-key index", cell(ok, "rule_noix", "maxi"), cell(ok, "rule_noix", "work")))
        bb = [r for r in ok if r.get("best_max") and r.get("best_work")]
        if bb:
            rows.append((f"{grp}, the {len(bb)} of at most {MAXDP} variables", "the rule", cell(bb, "rule", "maxi"), cell(bb, "rule", "work")))
            rows.append(("", "best", f"{int(max(r['best_max']['maxi'] for r in bb))} / {int(sum(r['best_max']['maxi'] for r in bb))}",
                         f"{int(max(r['best_work']['work'] for r in bb))} / {int(sum(r['best_work']['work'] for r in bb))}"))
            far = [r for r in bb if (r["rule"]["maxi"] > 10 * max(1, r["best_max"]["maxi"]) and r["rule"]["maxi"] >= 1e4)
                   or (r["rule"]["work"] > 10 * max(1, r["best_work"]["work"]) and r["rule"]["work"] >= 1e5)]
            notes.append(mctx("{grp}: {n} bodies under the rule have a largest intermediate over 10^4 and over 10 times the best order's, or work over 10^5 and over 10 times the best order's{some}.")
                         .format(grp=grp, n=len(far), some="".join(f", {r['stem']} `{r['name']}`" for r in far[:3])))
        missed = Counter(r.get("status", "") for r in B if r.get("status") != Status.OK)
        notes.append(mctx("{grp}: {n} bodies are not measured: {why}.")
                     .format(grp=grp, n=sum(missed.values()), why=", ".join(f"{k} {v}" for k, v in missed.most_common()) or "none"))
    return body(
        mctx("An algebra check applies once its labels are bound, and a function once the inputs of one of its modes are bound. The written order takes each variable at its first appearance; the rule's order takes each function output directly once a mode's inputs are bound, else the variable of the smallest relation, ties broken by the written order. The best order minimizes each measure over every order that the modes allow, for bodies of at most {n} variables. Each body is taken on the input where its written order has the largest intermediate. `unresolved` is a body that reads a relation the name map does not reach from the top level.")
        .format(n=MAXDP),
        table(("bodies", "order", "largest intermediate, max / sum", "work, max / sum"), rows),
        items(notes),
        ran(f"the rows of Prefix sizes, over the bodies of Join shapes of {corpus().files()}"))


JOIN_ORDERS = Section("Join orders", 2, True, join_orders)
