"""The part of `Solver` that finds the reached types and the dead clauses, and
writes the arcdata and the choice cases and witnesses."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from engine.program import (
    AdtType,
    AtomLiteral,
    Comparison,
    ConstructorTerm,
    DefinedName,
    Disjunction,
    NumberTerm,
    RecordTerm,
    RecordType,
    Variable,
    Wildcard,
    ComparisonOperator,
)
from dataclasses import replace as dc_replace
from arclog_convert import paths

from arclog_convert.forms import (
    Form,
    close,
    comment_text,
    directives,
    grid_param,
    params_to_amp,
    quote,
    read_without,
    without_repeats,
)
from arclog_convert.leaves import Written
from arclog_convert.lib import derive_proposer
from arclog_convert.terms import name_of


class CasesMixin:
    """The reached types, dead clauses, arcdata and choice cases and witnesses of a solver."""

    def type_values(self, tname: str) -> list[tuple[str, ...]]:
        """Every value of a case type, as the constructor names it holds."""
        import itertools
        t = self.c.find_type(tname, ())
        if isinstance(t, RecordType):
            return [sum(p, ()) for p in itertools.product(*(self.type_values(f.type.name) for f in t.fields))]
        if isinstance(t, AdtType) and tname in self.c.case_types:
            out = []
            for k in t.constructors:
                for p in itertools.product(*(self.type_values(f.type.name) for f in k.fields)):
                    out.append((k.name,) + sum(p, ()))
            return out
        return [()]

    def reached_types(self, tname: str) -> set[str]:
        """The case types a value of `tname` holds, itself included."""
        out: set[str] = set()
        todo = [tname]
        while todo:
            t = todo.pop()
            if t in out:
                continue
            decl = self.c.find_type(t, ())
            if isinstance(decl, RecordType):
                todo += [f.type.name for f in decl.fields]
            elif isinstance(decl, AdtType) and t in self.c.case_types:
                out.add(t)
                todo += [f.type.name for k in decl.constructors for f in k.fields]
        return out

    def ancestors(self, fname: str) -> list[tuple[str, str]]:
        """The points a nested point stands under, each with the
        constructor whose field holds it."""
        pts = self.c.point_fields()
        adt_of = {f_: adt_ for f_, adt_ in pts}
        out = []
        cur = fname
        while True:
            t = adt_of[cur].name
            parent = next(((f_, k.name) for f_, adt_ in pts for k in adt_.constructors
                           if any(fl.type.name == t for fl in k.fields)), None)
            if parent is None or parent in out:
                return out
            out.append(parent)
            cur = parent[0]

    def dead_clauses(self, main: list[Form], empty: set[str], mine: set[str], out: list[str],
                     others: set[str] = frozenset(), adds: set[str] | frozenset[str] = frozenset()) -> list[Form]:
        """The alt's rederivations of the concept relations whose clauses
        read a relation the alt derives no rows of: a clause that reads
        one positively is dead, a `NOT` of one holds and is dropped, and a
        relation all of whose clauses are dead is empty too. A clause whose
        head fixes one of `others`, the point's other constructors, holds
        no row in the alt, and its relation is rederived without it."""
        groups: dict[str, list[Form]] = defaultdict(list)
        fixed: set[str] = set()
        for f in main:
            if f.side != "DET" and set(f.branches) & others:
                fixed.add(f.name)
                continue
            groups[f.name].append(f)

        def touched(f: Form) -> bool:
            return bool((f.top_pos | f.top_neg | f.nested | f.reads) & empty)

        def rerender(f: Form):
            if f.src is None:
                inst, us, side = f.src_inst
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                gs = self.instance(inst, us, side, frozenset(empty))
                self.todo.pending, self.todo.kinds = saved
                if gs:
                    gs[0].comments = f.comments
                    gs[0].claim_slugs = f.claim_slugs
                return gs[0] if gs else None
            u, side, scope, sub, ns = f.src
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            g = self.clause(u, side, scope, sub, ns, drop_neg=frozenset(empty))
            self.todo.pending, self.todo.kinds = saved
            if g is not None:
                g.comments = f.comments
            return g

        # what this branch derives, with the concept's dead forms it revives;
        # a set of cases that holds this branch and no concept case revives
        # what it killed in the concept
        here = set(mine) | {"%" + n for n in self.c.case_set_unread if "%" + n not in empty}

        def revived(f: Form) -> bool:
            return (f.concept_dead or f.concept_form is not None) and bool(f.dead_reads & here)
        grew = True
        while grew:
            grew = False
            for f in main:
                if f.name not in here and revived(f):
                    here.add(f.name)
                    grew = True

        # what the concept leaves empty stays empty here unless this branch
        # derives it
        empty |= getattr(self, "concept_empty", set()) - here
        # a clause dead in the concept holds here only where this branch
        # derives what it reads
        groups = {n: [f for f in fs if not f.concept_dead or revived(f)] for n, fs in groups.items()}
        for name, fs in groups.items():
            if not fs and name not in mine:
                empty.add(name)

        def redone(fs: list[Form]) -> bool:
            return any(touched(f) or revived(f) for f in fs)

        changed = True
        while changed:
            changed = False
            for name, fs in groups.items():
                if name in empty or name in mine or not (redone(fs) or name in fixed):
                    continue
                if all(f.src is not None or f.src_inst is not None for f in fs) \
                        and all(touched(f) for f in fs) and all(rerender(f) is None for f in fs):
                    empty.add(name)
                    changed = True
        redo: list[Form] = []
        for name, fs in groups.items():
            if name in adds and name not in empty:
                # the case's own clauses of the relation stand beside these
                for f in fs:
                    g = rerender(f) if touched(f) and (f.src is not None or f.src_inst is not None) else f
                    if g is not None:
                        redo.append(g)
                continue
            if name in empty or name in mine or not (redone(fs) or name in fixed):
                continue
            for f in fs:
                if f.src is None and f.src_inst is None:
                    continue    # not rerendered: the concept's form stands
                elif touched(f):
                    g = rerender(f)
                    if g is not None:
                        redo.append(g)
                else:
                    redo.append(f)
        # a rederivation that repeats the column the concept leaves out
        # leaves it out too, and its readers read the concept's columns
        reps = getattr(self, "concept_repeats", {})
        narrow = {n for n in reps if n not in mine and not any(g.name == n for g in redo)}
        for i, g in enumerate(redo):
            if g.name in reps and all(x in g.head_repeat for x in reps[g.name].items()):
                redo[i] = without_repeats(g, reps[g.name])
                narrow.add(g.name)
        for i, g in enumerate(redo):
            for n in narrow & g.reads:
                lines = read_without(redo[i].lines, n, reps[n])
                if lines is not None:
                    redo[i] = dc_replace(redo[i], lines=lines)
        # a rederivation the same as the concept's is no rederivation
        concept_lines: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                concept_lines[f.name].append((f.concept_form or f).lines)
        redo_lines: dict[str, list] = defaultdict(list)
        for g in redo:
            redo_lines[g.name].append(g.lines)
        redo = [g for g in redo if g.name in adds or redo_lines[g.name] != concept_lines.get(g.name)]
        if "&out" in empty:
            out.append("    ;; TODO alt-undefined: every &output clause reads a relation this alt leaves empty")
            self.todo.kinds["alt-undefined"] += 1
        return redo

    # ---- arcdata

    def arcdata(self, rep, params, excludes, points, concept, derive_points, approx_w) -> str:
        out = [f";; {self.stem}", ""]
        if rep:
            parts = rep.split()
            out.append(f"(representative {parts[0]}" + (f" ${parts[1]}" if len(parts) > 1 else "") + ")")
            out.append("")
        out.extend(params)
        if params:
            out.append("")
        ex = self.choice_excludes(points)
        out.extend(ex + excludes)
        if ex or excludes:
            out.append("")
        wit = self.witness_file()
        used: set[str] = set()
        for slug, ws in approx_w.items():
            out.append(f"(approximated {slug}")
            for line in ws:
                out.extend(self.witness_form(line, wit, used, "  "))
            close(out, ")")
            out.append("")
        for fname, adt in points:
            prev_end = adt.span.first
            branches = []
            for k in adt.constructors:
                cm = []
                for ln in range(prev_end, k.span.first - 1):
                    t = comment_text(self.lines[ln])
                    if t is not None:
                        cm.append(t)
                prev_end = k.span.first
                ws = [(rest, ind) for d, rest, ind in directives(cm) if d == "witness"]
                if ws and k.name not in concept:
                    branches.append((k.name, ws))
            if not branches:
                continue
            out.append(f"(alts ${fname}")
            for bname, ws in branches:
                out.append(f"  (alt ${bname}")
                for rest, _ in ws:
                    out.extend(self.witness_form(rest, wit, used, "    "))
                close(out, ")")
            close(out, ")")
            out.append("")
        for amp, derives, side, dl_name in derive_points + self.store_points:
            out.append(f"(alts {amp}")
            # one derived side per proposer where the line gives several
            props = list(dict.fromkeys(map(derive_proposer, derives)))
            many = side == "Derived" and len(props) > 1
            for p_ in (props if many else [None]):
                alt = f"{amp}={p_}" if many else f"{amp}=${side}"
                out.append(f"  (alt {alt}")
                for d in derives:
                    prop = derive_proposer(d)
                    if many and prop != p_:
                        continue
                    rest = d.split(":", 1)[1].strip() if ":" in d else ""
                    rest = re.sub(r"^(\S+)\s+(derived|stored)\b", lambda m: f"{m.group(1)} {alt}", rest)
                    wid = f"{dl_name}={prop or 'stored'}"
                    out.extend(self.witness_form(f"{wid}: {rest}", wit, used, "    "))
                close(out, ")")
            close(out, ")")
            out.append("")
        return "\n".join(out).rstrip() + "\n"

    def choice_cases(self) -> set | None:
        """The value of each case impl_choice holds, as a nested tuple: a
        constructor `("$", name, args...)`, a record `("[]", fields...)`.
        Its clauses run over the relations whose own clauses run so, down
        to facts; None where a clause reads anything else."""
        prog = self.c.prog
        units: dict[str, list] = defaultdict(list)
        for u in prog.units:
            if not u.scope.components and not u.head.relation.instances:
                units[u.head.relation.name].append(u)

        class Unknown(Exception):
            pass

        def val(t, env):
            if isinstance(t, Variable):
                return env.get(t.name)
            if isinstance(t, ConstructorTerm):
                args = tuple(val(a, env) for a in t.args)
                return None if any(a is None for a in args) else ("$", t.name) + args
            if isinstance(t, RecordTerm):
                args = tuple(val(a, env) for a in t.args)
                return None if any(a is None for a in args) else ("[]",) + args
            if isinstance(t, NumberTerm):
                return ("#", t.value)
            if isinstance(t, DefinedName):
                return ("@", t.name)
            return None

        def unbound(t, env) -> bool:
            if isinstance(t, Variable):
                return t.name not in env
            if isinstance(t, (ConstructorTerm, RecordTerm)):
                return any(unbound(a, env) for a in t.args)
            return False

        def match(t, v, env):
            """env extended so that t is v, or None; `_` matches anything."""
            if isinstance(t, Wildcard):
                return env
            if isinstance(t, Variable):
                if t.name in env:
                    return env if env[t.name] == v else None
                return {**env, t.name: v}
            if isinstance(t, (ConstructorTerm, RecordTerm)):
                tag = ("$", t.name) if isinstance(t, ConstructorTerm) else ("[]",)
                if v[:len(tag)] != tag or len(v) != len(tag) + len(t.args):
                    return None
                for a, x in zip(t.args, v[len(tag):]):
                    env = match(a, x, env)
                    if env is None:
                        return None
                return env
            w = val(t, env)
            if w is None:
                raise Unknown
            return env if w == v else None

        memo: dict[str, list[tuple]] = {}
        busy: set[str] = set()

        def rows(name: str) -> list[tuple]:
            if name in memo:
                return memo[name]
            if name in busy or name not in units:
                raise Unknown
            busy.add(name)
            out_: list[tuple] = []
            for u in units[name]:
                for env in solve(u.body or (), [{}]):
                    r = tuple(val(a, env) for a in u.head.args)
                    if None in r:
                        raise Unknown
                    out_.append(r)
            busy.discard(name)
            memo[name] = out_
            return out_

        def solve(lits, envs):
            pending = list(lits)
            while pending:
                # a positive atom first, so the filters find their labels bound
                k = next((i for i, l in enumerate(pending) if isinstance(l, AtomLiteral) and not l.negated), 0)
                l = pending.pop(k)
                out = []
                if isinstance(l, AtomLiteral):
                    if l.atom.relation.instances:
                        raise Unknown
                    rs = rows(l.atom.relation.name)
                    for env in envs:
                        if l.negated and any(unbound(a, env) for a in l.atom.args):
                            raise Unknown
                        hits = []
                        for r in rs:
                            e = env
                            for a, v in zip(l.atom.args, r):
                                e = match(a, v, e) if e is not None else None
                            if e is not None:
                                hits.append(e)
                        if l.negated:
                            if not hits:
                                out.append(env)
                        else:
                            out.extend(hits)
                elif isinstance(l, Comparison) and l.op in (ComparisonOperator.EQ, ComparisonOperator.NE):
                    for env in envs:
                        a, b = val(l.lhs, env), val(l.rhs, env)
                        if a is None and b is None:
                            raise Unknown
                        g, t = (a, l.rhs) if a is not None else (b, l.lhs)
                        if l.op == ComparisonOperator.EQ:
                            e = match(t, g, env)
                            if e is not None:
                                out.append(e)
                        else:
                            if unbound(t, env):
                                raise Unknown
                            if match(t, g, env) is None:
                                out.append(env)
                elif isinstance(l, Disjunction):
                    for env in envs:
                        for br in l.branches:
                            out.extend(solve(br, [env]))
                else:
                    raise Unknown
                envs = out
            return envs

        try:
            return {r[0] for r in rows("impl_choice")}
        except Unknown:
            return None

    def choice_excludes(self, points) -> list[str]:
        if not points:
            return []
        facts = [u for u in self.c.prog.units if u.head.relation.name == "impl_choice" and not u.scope.components]
        if not facts:
            return []
        choice = self.c.find_type("Choice", ())
        direct = len(points) == 1 if isinstance(choice, AdtType) else len(points) == len(choice.fields)
        held = self.choice_cases()
        if held is None:
            self.todo.kinds["cases"] += 1
            return [";; TODO cases: impl_choice by a rule the script does not read"]
        import itertools

        def flat_names(v) -> tuple[str, ...]:
            if v[0] == "$":
                return (v[1],) + sum((flat_names(a) for a in v[2:]), ())
            if v[0] == "[]":
                return sum((flat_names(a) for a in v[1:]), ())
            return ()
        decl = next((r for r in self.c.prog.relations if r.name == "impl_choice" and not r.scope.components), None)
        lines = (self.comments_above(decl.span.first) if decl and decl.span else []) + self.comments_above(facts[0].span.first)
        reason = params_to_amp(" ".join(rest for d, rest, _ in directives(lines) if d == ""))
        if not reason:
            # the prose above a relation whose rows impl_choice's clauses leave out
            negs = [l.atom.relation.name for u in self.c.prog.units if u.head.relation.name == "impl_choice"
                    and not u.scope.components for l in u.body or ()
                    if isinstance(l, AtomLiteral) and l.negated and not l.atom.relation.instances]
            for n in dict.fromkeys(negs):
                r = self.c.rels.get(((), n))
                if r is not None and r.span:
                    reason += " ".join(rest for d, rest, _ in directives(self.comments_above(r.span.first)) if d == "")
            reason = params_to_amp(reason)
        why = f" {quote(reason)}" if reason else ""
        if not direct:

            parent: dict[str, str] = {}

            def values(tname: str, up: str | None = None) -> list[tuple[str, ...]]:
                t = self.c.find_type(tname, ())
                if isinstance(t, RecordType):
                    return [sum(p, ()) for p in itertools.product(*(values(f.type.name, up) for f in t.fields))]
                if isinstance(t, AdtType) and tname in self.c.case_types:
                    out_ = []
                    for k in t.constructors:
                        if up:
                            parent[k.name] = up
                        for p in itertools.product(*(values(f.type.name, k.name) for f in k.fields)):
                            out_.append((k.name,) + sum(p, ()))
                    return out_
                return [()]

            def closure(q: frozenset) -> frozenset:
                got_ = set(q)
                for n in q:
                    while n in parent:
                        n = parent[n]
                        got_.add(n)
                return frozenset(got_)
            got = {frozenset(flat_names(v)) for v in held}
            full_n = values("Choice")
            gone_n = [v for v in full_n if frozenset(v) not in got]
            # the fewest alts that fix each excluded case: a set of alts
            # stands where every case that takes them all is excluded
            order = {n: i for i, n in enumerate(dict.fromkeys(n for v in full_n for n in v))}
            full_s = [frozenset(v) for v in full_n]
            gone_s = {frozenset(v) for v in gone_n}
            parts = sorted({frozenset(sub) for g in gone_s for k in range(1, len(g) + 1)
                            for sub in itertools.combinations(sorted(g, key=order.__getitem__), k)},
                           key=lambda q: (len(q), sorted(order[n] for n in q)))
            cl = {q: closure(q) for q in parts}
            shortest: dict[frozenset, int] = {}   # each closure: the fewest alts of a part that has it
            for q in parts:
                shortest[cl[q]] = min(shortest.get(cl[q], len(q)), len(q))
            chosen: list[frozenset] = []
            for q in parts:
                if cl[q] != q and shortest[cl[q]] < len(q):
                    continue
                if any(cl[c] <= cl[q] for c in chosen):
                    continue
                if all(c in gone_s for c in full_s if q <= c):
                    chosen.append(q)
            return [f"(exclude ({' '.join('$' + n for n in sorted(q, key=order.__getitem__))}){why})"
                    for q in chosen]
        cases = {tuple(p[1] for p in (v[1:] if v[0] == "[]" else (v,))) for v in held}
        ctors = [[k.name for k in adt.constructors] for _, adt in points]
        full = set(itertools.product(*ctors))
        gone = full - cases
        if not gone:
            return []
        # the fewest alts that fix each excluded combination: a partial
        # choice stands where every completion of it is excluded
        n = len(ctors)
        picks: list[dict[int, str]] = []
        for size in range(1, n + 1):
            for idx in itertools.combinations(range(n), size):
                for vals in itertools.product(*(ctors[i] for i in idx)):
                    part = dict(zip(idx, vals))
                    if any(all(part.get(i) == p[i] for i in p) for p in picks):
                        continue
                    if all(c in gone for c in full if all(c[i] == v for i, v in part.items())):
                        picks.append(part)
        return [f"(exclude ({' '.join('$' + p[i] for i in sorted(p))}){why})" for p in picks]

    def witness_file(self) -> list[dict]:
        p = paths.WITNESSES / f"{self.stem}.wit.json"
        if not p.exists():
            return []
        return json.loads(p.read_text())["witnesses"]

    def assign_form(self, amp: str, v) -> str:
        """A witness's reassignment of a relation, its rows in the form a
        param form takes: a picture as a grid, facts as rows, and the rows
        of a relation with a Position column as grids."""
        def arg(a) -> str:
            return "(" + " ".join(map(arg, a)) + ")" if isinstance(a, list) else str(a)
        ts = self.param_types.get(amp, [])
        head = f"(assign {amp}"
        if isinstance(v, dict) and "grid" in v:
            ar, ac = v.get("anchor", [-1, -1])
            rows = ["(" + " ".join(("@" if (i, j) == (ar, ac) else "") + str(x) for j, x in enumerate(r)) + ")"
                    for i, r in enumerate(v["grid"])]
            return "\n".join([head, "  (grid", *("    " + r for r in rows)]) + "))"
        if "Position" in ts and v and all(isinstance(r, list) and not any(isinstance(x, list) for x in r) for r in v) \
                and not all(len(r) == len(ts) for r in v):
            # a picture of the relation's frame
            return "\n".join([head, "  (grid", *("    " + arg(r) for r in v)]) + "))"
        order = self.type_order.get(amp)
        if order is not None:
            v = [[r[i] for i in order] if isinstance(r, list) and len(r) == len(order) else r for r in v]
        rest = " " + " ".join(arg(r) for r in v) + ")"
        return grid_param(head, ts, rest) or head + rest

    def witness_form(self, rest: str, wit, used: set[str], ind: str) -> list[str]:
        """A witness from its @witness line `<id>: <plausibility> <verdict>`
        and nested lines, with its grids from the witness file."""
        m = re.match(r"([\w=.-]+):\s*(\S+)\s+(\S+)\s*(.*)", rest)
        if not m:
            return [f"{ind};; TODO witness-line: {rest}"]
        wid, plaus, verdict, more = m.groups()
        verdict = name_of(verdict, self.many)
        head = f"{ind}(witness {wid} {plaus} {verdict}"
        if wid in used:
            return [head + ")"]
        used.add(wid)
        lines = [head]
        for rel in re.findall(r"@relaxed\s+([\w-]+)", more):
            lines.append(f"{ind}  (relaxed {rel})")
        w = next((x for x in wit if x["id"] == wid), None)
        if w is None:
            self.todo.add("witness-missing", f"{wid}: the witness file holds no witness of this id")
            close(lines, ")")
            return [ind + t for t in self.todo.take()] + lines
        lines.append(f"{ind}  (separates {quote(params_to_amp(w.get('separates', '')))})")
        for k, v in (w.get("assign") or {}).items():
            at = self.c.names.get((("Params",), k)) if k in self.c.rigid else None   # a placed relation: `block.part`
            amp = self.c.wrote(f"&{at or k}", Written(("Params",), k, False))
            lines.extend(f"{ind}  {l}" for l in self.assign_form(amp, v).split("\n"))
        lines.append(f"{ind}  (input (grid")
        lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in w["input"])
        close(lines, "))")
        outs = w["output"]
        if isinstance(outs, list) and outs and isinstance(outs[0], dict):
            for g in outs:
                names = " ".join(name_of(n, self.many) for n in g["cases"])
                grid = g["grid"]
                if grid is None:
                    lines.append(f"{ind}  (output {names} undefined)")
                elif grid and isinstance(grid[0][0], list):
                    lines.append(f"{ind}  (output {names}")
                    for gr in grid:
                        lines.append(f"{ind}    (grid")
                        lines.extend(f"{ind}      ({' '.join(map(str, r))})" for r in gr)
                        close(lines, ")")
                    close(lines, ")")
                else:
                    lines.append(f"{ind}  (output {names} (grid")
                    lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in grid)
                    close(lines, "))")
        else:
            lines.append(f"{ind}  (output (grid")
            lines.extend(f"{ind}    ({' '.join(map(str, r))})" for r in outs)
            close(lines, "))")
        close(lines, ")")
        return lines

