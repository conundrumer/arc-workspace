"""The part of `Solver` that renders the forms: the state combinations, the
sinks and the choice rendering."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from engine.program import AdtType, AtomLiteral, GridCall
from dataclasses import replace as dc_replace
from typing import TYPE_CHECKING

from arclog_convert.forms import (
    Form,
    MERGES,
    MERGES_UNMERGED,
    close,
    comment_text,
    demo_lines,
    directives,
    merge_forms,
    params_to_amp,
    quote,
    read_without,
    render_forms,
    topo,
    without_repeats,
)
from arclog_convert.terms import ctor_names

if TYPE_CHECKING:
    from arclog_convert.solver import Claim


PROPOSED = re.compile(r'\((?:DET|DET_OR_RULE|RULE_OR_DET) (&\w+)(?: "(?:[^"\\]|\\.)*")? [A-Z]')
"""The line of a relation that a proposer determines: its name, then the
proposer's, after a gloss where the line has one."""


class RenderMixin:
    """The rendering of a solver's forms, its state combinations, sinks and choices."""

    # ---- placement and rendering

    def render(self, forms: list[Form], claims: list[Claim], points, concept, all_ctors) -> str:
        slugs = [cl.slug for cl in claims]
        idx = {s: i for i, s in enumerate(slugs)}
        # An instance whose inputs fix the constructors of several cases
        # stands in the concept with the inputs the concept's case admits.
        extra: list[Form] = []
        for f in forms:
            if f.src_inst is None or not (set(f.branches) - concept):
                continue
            inst, us, side = f.src_inst

            def unit_ctors(u) -> set[str]:
                args = list(u.head.args) + [a for l in u.body or () if isinstance(l, AtomLiteral) and not l.negated
                                            for a in l.atom.args]
                return {n for a in args for n in ctor_names(a) if n in all_ctors}
            mine_us = [u for u in us if unit_ctors(u) <= concept]
            if not any(u.body is not None and unit_ctors(u) for u in mine_us):
                continue   # no input of the concept's own case: the instance is the alts'
            if not mine_us or len(mine_us) == len(us):
                continue
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            gs = self.instance(inst, mine_us, side)
            self.todo.pending, self.todo.kinds = saved
            if gs:
                g = self.settled(gs[0])
                g.comments, g.claim_slugs = f.comments, f.claim_slugs
                g.branches = tuple(sorted(set(g.branches) & concept))
                g.src_inst = (inst, mine_us, side)
                extra.append(g)
        forms = forms + extra
        main = [f for f in forms if not (set(f.branches) - concept)]
        branch_forms = [f for f in forms if set(f.branches) - concept]
        main, branch_forms = self.sink(main, branch_forms, claims, concept)
        main, branch_forms = self.drop_repeats(main, branch_forms, concept)
        # a concept clause that reads a relation only alts derive holds in no
        # concept model
        derived = {f.name for f in main}
        # only clauses whose heads fix an alt's constructor; an instance, a
        # parameter or a form the concept shares is not alt-only
        def form_scope(f: Form):
            if f.src is not None:
                return f.src[2]
            return f.src_inst[0].scope.components if f.src_inst is not None else None
        alt_only = {f.name for f in branch_forms} - derived - \
            {f.name for f in branch_forms if form_scope(f) in (None, ("Params",))}
        # a parameter with stored values has them in the concept, whatever the
        # determination derives it as under an alt
        stored = {m.relation.name for m in self.c.prog.macros
                  if isinstance(m, GridCall) and m.scope.components == ("Params",)}
        stored |= {u.head.relation.name for u in self.c.prog.units if u.scope.components == ("Params",)
                   and not u.head.relation.instances and not u.body}
        stored_names = {self.c.rel_name(("Determine",), n) for n in stored}
        alt_only -= stored_names
        # a set of cases that holds no concept case is empty in the concept
        alt_only |= {"%" + n for n in self.c.case_set_unread}
        # Each clause and instance that reads such a relation is written again
        # with that relation empty: a positive read kills its list, a NOT of
        # it is dropped, and a form left with nothing holds no concept row.
        # The emptiness spreads to the relations whose every form is dead.
        bare: set[int] = set()   # the forms whose concept form is a stored `DET` with no body
        changed = True
        while changed:
            changed = False
            for f in main:
                if f.concept_dead or (f.src is None and f.src_inst is None):
                    continue
                dr = frozenset((f.reads | f.top_pos | f.top_neg | f.nested) & alt_only)
                if dr == f.dead_reads:
                    continue
                f.dead_reads = dr
                changed = True
                saved = list(self.todo.pending), Counter(self.todo.kinds)
                if f.src_inst is not None:
                    inst, us, side = f.src_inst
                    gs = self.instance(inst, us, side, dr)
                    g = gs[0] if gs else None
                else:
                    u, side, scope, sub, ns = f.src
                    g = self.clause(u, side, scope, sub, ns, drop_neg=dr)
                g = self.settled(g)
                self.todo.pending, self.todo.kinds = saved
                bare.discard(id(f))
                if g is None and f.name in stored_names and f.side == "DET":
                    # the concept's values are the stored ones, which no determination derives
                    one = " (ONE)" if f.name in self.open_amps() else ""
                    g = Form([f"(DET {f.name}{one})"], f.name, set(), line=f.line)
                    g.marks = ["(ONE)"] if one else []
                    bare.add(id(f))
                if g is None:
                    f.concept_dead, f.concept_form = True, None
                    continue
                g.comments, g.claim_slugs = f.comments, f.claim_slugs
                f.concept_form = g if g.lines != f.lines else None
            gone = {n for n in derived if all(g.concept_dead for g in main if g.name == n)} - alt_only - stored_names
            if gone:
                alt_only |= gone
                changed = True
        # a `DET` with no body and no proposer, on no port, is a fault of the conversion
        proposed = {m.group(1) for g in forms if g.src is None and g.src_inst is None and g.lines
                    and (m := PROPOSED.match(g.lines[0]))}
        for f in main:
            if id(f) in bare and f.name not in proposed:
                pending, self.todo.pending = self.todo.pending, []
                self.todo.add("det-no-body", f"{f.name}: the relation has no body and no proposer")
                target = f.concept_form or f
                target.comments = target.comments + self.todo.take()
                self.todo.pending = pending
        self.concept_empty = alt_only
        self.drop_concept_repeats(main)
        self.render_main = main
        main = [f.concept_form or f for f in main if not f.concept_dead]
        main = self.sink_demo(main, branch_forms, claims)
        self.c.note_writing(main, frozenset())
        # dependency closure: each relation goes under the first claim among its readers' claims
        by_name: dict[str, list[Form]] = defaultdict(list)
        for f in main:
            by_name[f.name].append(f)
        claim_of: dict[str, int] = {}
        for f in main:
            ks = [idx[s] for s in f.claim_slugs if s in idx]
            if ks:
                claim_of[f.name] = min(min(ks), claim_of.get(f.name, 99))
        # params named in claim text
        for i, cl in enumerate(claims):
            for m in re.finditer(r"&(\w+)", cl.text):
                n = "&" + m.group(1)
                claim_of[n] = min(i, claim_of.get(n, 99))
        def close_claims() -> None:
            changed = True
            while changed:
                changed = False
                for f in main:
                    if f.name not in claim_of:
                        continue
                    for r in f.reads:
                        if r in by_name and claim_of.get(r, 99) > claim_of[f.name]:
                            claim_of[r] = claim_of[f.name]
                            changed = True
        close_claims()
        # a relation no claim reads, and that an alt's form reads, stands
        # under the claim the reading form serves, or else the last claim:
        # the tail stands after the ALTS forms
        if claims:
            for f in main:
                if f.name in claim_of:
                    continue
                readers = [g for g in branch_forms if f.name in g.reads and g.name != f.name]
                if not readers:
                    continue
                ks = [idx[s] for g in readers for s in g.claim_slugs if s in idx] + \
                     [claim_of[g.name] for g in readers if g.name in claim_of]
                claim_of[f.name] = min(ks) if ks else len(claims) - 1
            close_claims()
        # a relation stands under the first claim that reads it: one that the
        # solver's @claim puts before every claim reading it moves to the first
        named_ = {"&" + m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        # a parameter stands under the first claim whose text names it, or
        # under the first claim that reads it where that claim comes earlier
        changed = True
        while changed:
            changed = False
            for n in named_ & set(by_name):
                namer = min(i for i, cl in enumerate(claims) if re.search(rf"{re.escape(n)}(?!\w)", cl.text))
                rs = [claim_of[g.name] for g in main if n in g.reads and g.name != n and g.name in claim_of]
                if claim_of.get(n) != min([namer, *rs]):
                    claim_of[n] = min([namer, *rs])
                    changed = True
            for f in main:
                if f.name not in claim_of or f.name in named_:
                    continue
                rs = [claim_of[g.name] for g in main if f.name in g.reads and g.name != f.name and g.name in claim_of]
                if rs and min(rs) > claim_of[f.name]:
                    claim_of[f.name] = min(rs)
                    changed = True
        self.claim_of_name = {n: claims[i].slug for n, i in claim_of.items() if i < len(claims)}
        # a relation's dependencies come before it
        order = topo(main)
        blocks: dict[int, list[Form]] = defaultdict(list)
        tail: list[Form] = []
        for f in order:
            if f.name in claim_of:
                blocks[claim_of[f.name]].append(f)
            else:
                tail.append(f)
        self.tail_names = {f.name for f in tail}
        out = [f";; {self.stem}", ""]
        if self.c.demo_select:
            self.todo.kinds["demonstrated-select"] += 1
            out += [";; TODO demonstrated-select: the program reads a demonstrated rule by its constructor, so it",
                    ";; selects a rule, and a DEMONSTRATED form names no rule", ""]
        for i, cl in enumerate(claims):
            fs = blocks.get(i, [])
            out.append(f"({cl.kind} {cl.slug} {quote(cl.text)}")
            if cl.approx:
                out.append(f"  (APPROXIMATED {quote(cl.approx)})")
            body = render_forms(fs, "  ")
            if body:
                out.append("")
                out.extend(body)
            close(out, ")")
            out.append("")
        # ALTS forms
        choice_at = len(out)
        self.render_args = (branch_forms, concept, claims, self.render_main)
        for fname, adt in points:
            anc = self.ancestors(fname)
            if anc:
                continue      # rendered inside its branch
            out.extend(self.render_choice(fname, adt, branch_forms, concept, claims, self.render_main))
        branch_names = {f.name for f in branch_forms}
        late: set[str] = set()
        changed = True
        while changed:
            changed = False
            for f in tail:
                if f.name not in late and (f.name == "&out" or f.reads & (branch_names | late)):
                    late.add(f.name)
                    changed = True
        if claims:
            out.extend(render_forms(tail, ""))
        else:
            out = out[:choice_at] + render_forms([f for f in tail if f.name not in late], "") + \
                ([""] if any(f.name not in late for f in tail) else []) + out[choice_at:]
            out.extend(render_forms([f for f in tail if f.name in late], ""))
        return self.state_combinations("\n".join(out).rstrip() + "\n", points)

    def state_combinations(self, text: str, points) -> str:
        """The text with a nested ALT for each combination of alts of
        different points that each rederive a relation: the nested ALT
        states the relation as the combination's case derives it."""
        from arclog_convert.lint import L as LintL, Sym as LintSym, alt_points, flat, placements, read as lint_read, \
            unstated_combinations
        branch_forms, concept, _, main = self.render_args
        main_text: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                main_text[f.name].append((f.concept_form or f).lines)
        saved = list(self.todo.pending), Counter(self.todo.kinds)
        excludes = self.choice_excludes(points)
        self.todo.pending, self.todo.kinds = saved
        excluded = [frozenset(re.findall(r"\$\w+", m.group(1)))
                    for x in excludes if (m := re.match(r"\(exclude \(([^)]*)\)", x))]
        tail_names = getattr(self, "tail_names", set()) | {"&out"}
        done: set[frozenset] = set()
        while True:
            forms = lint_read(text)
            point, under = alt_points(forms)
            sites: dict[frozenset, set[str]] = defaultdict(set)
            for n, case, _ in unstated_combinations(placements(forms), forms, excluded):
                if case not in done:
                    sites[case].add(n)
            if not sites:
                return text
            # each alt's own block, a direct child of its ALTS form
            top: dict[str, LintL] = {}

            def find(xs) -> None:
                for f in xs:
                    if not isinstance(f, LintL):
                        continue
                    if f.head == "ALTS":
                        for a in f.items[2:]:
                            if isinstance(a, LintL) and a.head == "ALT" and isinstance(a.items[1], LintSym):
                                top.setdefault(a.items[1].text, a)
                    find(f.items)
            find(forms)
            # the combinations in the order of their alts' blocks
            case = min(sites, key=lambda c: (len(c), sorted(top[a].start if a in top else -1 for a in c)))
            done.add(case)
            if not all(a in top for a in case):
                continue

            def ancestors_of(a: str) -> set[str]:
                got, pt = set(), point[a]
                while (up := under.get(pt)) is not None:
                    got.add(up)
                    pt = point[up]
                return got
            implied = set().union(*(ancestors_of(a) for a in case))
            first = min((a for a in case if a not in implied), key=lambda a: top[a].start)
            chain = sorted(case - {first} - ancestors_of(first), key=lambda a: top[a].start)
            alts = [(point[a][1:], a[1:]) for a in case]
            todo_out: list[str] = []
            fs, _ = self.alt_case(alts, branch_forms, concept, main, main_text, todo_out)
            rels = sites[case]
            new = [f for f in fs if f.name in rels]
            new += [f for f in main if f.name in rels - {g.name for g in fs} and not f.concept_dead]
            if not new:
                continue
            # a form of the case that the new forms read, directly or through
            # other such forms, joins them where no block the case sees states
            # it, or the deepest such block states it in other text
            visible = [p for p in placements(forms) if p.name and set(p.alts) <= case]
            seen: dict[str, set[str]] = {}
            for p in visible:
                name = p.name.partition(".")[0]
                deepest = max(len(q.alts) for q in visible if q.name.partition(".")[0] == name)
                if len(p.alts) == deepest:
                    seen.setdefault(name, set()).add(flat(p.form))

            def stated_otherwise(g: Form) -> bool:
                return g.name not in seen or flat(lint_read("\n".join(g.lines))[0]) not in seen[g.name]
            want = set().union(*(f.reads for f in new))
            while more := [g for g in fs if g.name in want and stated_otherwise(g) and not any(g is h for h in new)]:
                new += more
                want |= set().union(*(g.reads for g in more))
            # the deepest block of the chain that the file holds
            block, rest = top[first], list(chain)
            while rest:
                nxt = next((x for x in block.items[2:] if isinstance(x, LintL) and x.head == "ALT"
                            and isinstance(x.items[1], LintSym) and x.items[1].text == rest[0]), None)
                if nxt is None:
                    break
                block, rest = nxt, rest[1:]
            col = block.start - text.rfind("\n", 0, block.start) - 1
            ind = " " * (col + 2)
            # the combination's forms serve the innermost alt's claims, and
            # stand in its first output block
            cl = self.ctor_claims((chain[-1] if chain else first)[1:])
            home = next((x for x in cl if x[0] == "OUTPUT"), cl[0] if cl else None)
            inner = [g for g in new if g.name not in tail_names] if home is not None else []
            bare = [g for g in new if not any(g is h for h in inner)]
            if not rest:
                # the file holds the combination's block: its forms join it
                claim = next((x for x in block.items[2:] if isinstance(x, LintL) and x.head in ("INPUT", "OUTPUT")
                              and home is not None and isinstance(x.items[1], LintSym)
                              and x.items[1].text == home[1]), None)
                edits = []
                if bare:
                    edits.append((block.end - 1, render_forms(topo(bare), ind)))
                if inner and claim is not None:
                    edits.append((claim.end - 1, render_forms(topo(inner), ind + "  ")))
                elif inner and home is not None:
                    lines = [f"{ind}({home[0]} {home[1]} {quote(home[2])}"] + \
                        render_forms(topo(inner), ind + "  ")
                    close(lines, ")")
                    nm = block.items[1]
                    edits.append((nm.pos + len(nm.text), lines))
                for at, lines in sorted(edits, reverse=True):
                    text = text[:at] + "\n" + "\n".join(lines) + text[at:]
                continue
            lines = []
            for b in rest:
                lines.append(f"{ind}(ALT {b}")
                ind += "  "
            lines.extend(ind + x for x in todo_out if x.strip().startswith(";;"))
            if inner and home is not None:
                lines.append(f"{ind}({home[0]} {home[1]} {quote(home[2])}")
                lines.extend(render_forms(topo(inner), ind + "  "))
                close(lines, ")")
            lines.extend(render_forms(topo(bare), ind))
            close(lines, ")" * len(rest))
            at = block.end - 1
            text = text[:at] + "\n" + "\n".join(lines) + text[at:]

    def sink_demo(self, main: list[Form], branch_forms: list[Form], claims) -> list[Form]:
        """Each form that only one DEMO_RULE reads, moved into it."""
        named = {m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        for d in [f for f in main if f.demo]:
            rule_reads = {rule: reads for rule, _, _, reads, _ in d.demo}
            # a clause whose head names a rule is that rule's
            own = {id(g): g.demo_rule for g in main if g.demo_rule in rule_reads}
            assign: dict[str, str] = {}
            changed = True
            while changed:
                changed = False
                for g in main:
                    if g is d or g.demo or g.name in assign or g.name == "&out" or g.name[1:] in named \
                            or g.claim_slugs or id(g) in own:
                        continue
                    if any(h.name == g.name and h is not g for h in main):
                        continue
                    who: set[str] = set()
                    for h in main + branch_forms:
                        if h is d:
                            if g.name in d.demo_input_reads:
                                who.add("")
                            who |= {r for r, rs in rule_reads.items() if g.name in rs}
                        elif h.name != g.name and g.name in h.reads:
                            who.add(own.get(id(h)) or assign.get(h.name, ""))
                    if len(who) == 1 and "" not in who:
                        assign[g.name] = next(iter(who))
                        changed = True
            if not assign and not own:
                continue
            helpers: dict[str, list[Form]] = defaultdict(list)
            moved = [g for g in main if g.name in assign or id(g) in own]
            for g in moved:
                helpers[own.get(id(g)) or assign[g.name]].append(g)
            d.lines = d.demo_head + demo_lines(d.demo, helpers)
            d.reads = (d.reads | set().union(*(g.reads for g in moved))) - {g.name for g in moved}
            main = [g for g in main if not any(g is x for x in moved)]
        return main

    def drop_repeats(self, main: list[Form], branch_forms: list[Form], concept):
        """A concept relation whose head repeats a column that an alt's
        clause varies leaves the repeat out: the concept's readers read the
        column it repeats, and the alt rederives them with its own columns."""
        for f in list(main):
            if not f.head_repeat or f.side != "RULE" or sum(g.name == f.name for g in main) != 1:
                continue
            alts = [g for g in branch_forms if g.name == f.name]
            if not alts:
                continue
            bs = set().union(*(set(g.branches) - concept for g in alts))
            drop = dict(f.head_repeat)   # the dropped column -> the column it repeats
            new = without_repeats(f, drop)
            main[main.index(f)] = new
            for g in list(main):
                if g is new or not any(f"({f.name} " in l or f"({f.name})" in l for l in g.lines):
                    continue
                lines = read_without(g.lines, f.name, drop)
                if lines is None or lines == g.lines:
                    continue
                main[main.index(g)] = dc_replace(g, lines=lines)
                branch_forms.append(dc_replace(g, branches=tuple(sorted(set(g.branches) | bs))))
            # an alt's reader that the rederiving alts leave alone reads the
            # concept's columns, and their combination rederives it
            for g in list(branch_forms):
                if g.name == f.name or set(g.branches) & bs or \
                        not any(f"({f.name} " in l or f"({f.name})" in l for l in g.lines):
                    continue
                lines = read_without(g.lines, f.name, drop)
                if lines is None or lines == g.lines:
                    continue
                branch_forms[branch_forms.index(g)] = dc_replace(g, lines=lines)
                branch_forms.append(dc_replace(g, branches=tuple(sorted(set(g.branches) | bs))))
        return main, branch_forms

    def drop_concept_repeats(self, main: list[Form]) -> None:
        """A concept form whose head repeats a column where the full form,
        with the alts' reads, varies it leaves the repeat out: the concept's
        readers read the column it repeats, and each alt that revives the
        form rederives them with its own columns."""
        self.concept_repeats: dict[str, dict[str, str]] = {}   # relation -> the dropped column -> the one it repeats
        for f in main:
            g = f.concept_form
            if f.concept_dead or g is None or f.side != "RULE" or sum(h.name == f.name for h in main) != 1:
                continue
            drop = {x: y for x, y in g.head_repeat if (x, y) not in f.head_repeat}
            if not drop:
                continue
            f.concept_form = without_repeats(g, drop)
            self.concept_repeats[f.name] = drop
            for r in main:
                if r is f or r.concept_dead:
                    continue
                base = r.concept_form or r
                if not any(f"({f.name} " in l or f"({f.name})" in l for l in base.lines):
                    continue
                lines = read_without(base.lines, f.name, drop)
                if lines is None or lines == base.lines:
                    continue
                r.concept_form = dc_replace(base, lines=lines)
                r.dead_reads = r.dead_reads | {f.name}

    def sink(self, main: list[Form], branch_forms: list[Form], claims, concept):
        """Each concept form that only one alt's forms read, moved into
        that alt."""
        named = {m.group(1) for cl in claims for m in re.finditer(r"&(\w+)", cl.text)}
        moved: dict[str, frozenset[str]] = {}
        changed = True
        while changed:
            changed = False
            names = defaultdict(list)
            for f in main:
                names[f.name].append(f)
            for name, fs in names.items():
                if name in moved or name == "&out" or name[1:] in named:
                    continue
                if any(f.claim_slugs for f in fs):
                    continue
                readers = [f for f in main + branch_forms if name in f.reads and f.name != name]
                if not readers:
                    continue
                sets = []
                for r in readers:
                    if r.name in moved:
                        sets.append(moved[r.name])
                    elif set(r.branches) - concept:
                        sets.append(frozenset(set(r.branches) - concept))
                    else:
                        sets = []
                        break
                if not sets:
                    continue
                common = frozenset.intersection(*sets)
                if common:
                    moved[name] = common
                    changed = True
        if not moved:
            return main, branch_forms
        # a concept form that the branch derives again is read nowhere
        dead = {n for n, k in moved.items()
                if any(g.name == n and k <= set(g.branches) - concept for g in branch_forms)}
        main = [f for f in main if f.name not in dead]
        for f in main:
            if f.name in moved:
                f.branches = tuple(sorted(set(f.branches) | moved[f.name]))
        return [f for f in main if f.name not in moved], branch_forms + [f for f in main if f.name in moved]

    def ctor_claims(self, name: str) -> list[tuple[str, str, str]]:
        """The claim readings the @scene and @rule lines under a
        constructor give: (kind, slug, text)."""
        for _, adt in self.c.point_fields():
            prev = adt.span.first
            for k in adt.constructors:
                if k.name == name:
                    cm = [t for ln in range(prev, k.span.first - 1)
                          if (t := comment_text(self.lines[ln])) is not None]
                    out = []
                    for d, rest, _ in directives(cm):
                        m = re.match(r"([\w-]+):\s*(.*)", rest) if d in ("scene", "rule") else None
                        if m:
                            out.append(("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
                    return out
                prev = k.span.first
        return []

    def render_choice(self, fname, adt: AdtType, branch_forms, concept, claims, main,
                      inherited: dict[str, list] | None = None) -> list[str]:
        """The ALTS form of the point `fname`. `inherited` holds, for a point
        that exists only under an alt, each relation's lines as that alt's
        case derives them."""
        all_ctors_field = {k.name: fname for k in adt.constructors}
        decl_line = adt.span.first
        gloss = self.gloss_at(decl_line)
        ctors = adt.constructors
        out = [f"(ALTS ${fname} {quote(params_to_amp(gloss))} ${ctors[0].name}"]
        prev_end = decl_line
        ctor_comments = {}
        for k in ctors:
            # comments between the previous constructor and this one
            cm = []
            for ln in range(prev_end, k.span.first - 1):
                t = comment_text(self.lines[ln])
                if t is not None:
                    cm.append(t)
            ctor_comments[k.name] = cm
            prev_end = k.span.first
        main_text: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                main_text[f.name].append((f.concept_form or f).lines)
        if inherited is not None:
            main_text = defaultdict(list, inherited)
        # the points that exist only with the concept's branch stand in its block
        subs = [(f2, adt2) for f2, adt2 in self.c.point_fields()
                if (a2 := self.ancestors(f2)) and a2[0] == (fname, ctors[0].name)]
        if subs:
            out.append(f"  (ALT ${ctors[0].name}")
            for f2, adt2 in subs:
                sub_lines = self.render_choice(f2, adt2, *self.render_args, inherited=inherited)
                out.extend("    " + l if l else l for l in sub_lines if l)
            close(out, ")")
        for k in ctors[1:]:
            ds = directives(ctor_comments[k.name])
            bclaims = []
            for d, rest, _ in ds:
                if d in ("scene", "rule"):
                    m = re.match(r"([\w-]+):\s*(.*)", rest)
                    if m:
                        bclaims.append(("INPUT" if d == "scene" else "OUTPUT", m.group(1), params_to_amp(m.group(2))))
            # a form that this branch shares with other branches of this point
            # is this branch's, and stands in each of their blocks
            # the constructors this point stands under are fixed in its blocks
            sib = {kk.name for kk in ctors} | {ck for _, ck in self.ancestors(fname)}
            nested = [f for f in branch_forms if k.name in f.branches and (set(f.branches) - concept - sib)]
            out.append(f"  (ALT ${k.name}")
            fs, case_text = self.alt_case([(fname, k.name)], branch_forms, concept, main, main_text, out)
            claim_slugs = {s for _, s, _ in bclaims}
            placed: dict[str, list[Form]] = defaultdict(list)
            rest_forms = []
            tgt_of: dict[str, str | None] = {}
            for f in fs:
                if f.name in tgt_of:
                    tgt = tgt_of[f.name]
                    (placed[tgt] if tgt else rest_forms).append(f)
                    continue
                tgt = next((s for s in f.claim_slugs if s in claim_slugs), None)
                if tgt is None:
                    # the claim block of the concept form with this name
                    tgt = self.claim_of_name.get(f.name) if hasattr(self, "claim_of_name") else None
                    if tgt not in claim_slugs:
                        tgt = None
                tgt_of[f.name] = tgt
                if tgt:
                    placed[tgt].append(f)
                else:
                    rest_forms.append(f)
            # a form that a claim block's form reads stands in the first such block
            tail_names = getattr(self, "tail_names", set()) | {"&out"}
            moved_ = True
            while moved_:
                moved_ = False
                for f in list(rest_forms):
                    if f.name in tail_names:
                        continue
                    tgt = next((sl for _, sl, _ in bclaims
                                if any(f.name in g.reads for g in placed.get(sl, []))), None)
                    if tgt is not None:
                        rest_forms = [g for g in rest_forms if g.name != f.name]
                        placed[tgt].extend(g for g in fs if g.name == f.name and g not in placed[tgt])
                        tgt_of[f.name] = tgt
                        moved_ = True
            # any other form that is no tail form serves the claims the alt
            # reads: it stands in the alt's first output block
            home = next((sl for kd, sl, _ in bclaims if kd == "OUTPUT"), bclaims[0][1] if bclaims else None)
            if home is not None:
                for f in [g for g in rest_forms if g.name not in tail_names]:
                    placed[home].append(f)
                    tgt_of[f.name] = home
                rest_forms = [g for g in rest_forms if g.name in tail_names]
            for kind, slug, text in bclaims:
                out.append(f"    ({kind} {slug} {quote(text)}")
                body = render_forms(topo(placed.get(slug, [])), "      ")
                if body:
                    out.extend(body)
                close(out, ")")
            body = render_forms(rest_forms, "    ")
            out.extend(body)
            # a combination with a later point's branch stands nested under this branch
            order = {kk.name: i for _, a_ in self.c.point_fields() for i, kk in enumerate(a_.constructors)}
            field_of = {kk.name: f_ for f_, a_ in self.c.point_fields() for kk in a_.constructors}
            pidx = {f_: i for i, (f_, _) in enumerate(self.c.point_fields())}
            combos: dict[tuple[str, ...], list[Form]] = defaultdict(list)
            under_k = {f2 for f2, _ in self.c.point_fields() if (fname, k.name) in self.ancestors(f2)}
            for f in nested:
                others = tuple(sorted(set(f.branches) - concept - sib, key=lambda b: (pidx[field_of[b]], order[b])))
                if all(field_of[b] in under_k for b in others):
                    continue   # a point that exists only with this branch renders it
                # the combination stands under the branch of its first point
                if all(pidx[field_of[b]] > pidx[fname] for b in others):
                    combos[others].append(f)
                elif not any(pidx[field_of[b]] < pidx[fname] for b in others):
                    out.append(f"    ;; TODO combination: {' & '.join('$' + b for b in f.branches)}")
                    self.todo.kinds["combination"] += 1
                    out.extend(render_forms([f], "    "))
            for others, cfs in combos.items():
                # a relation the combination derives as the other branch
                # alone does is no rederivation
                alone: dict[str, list] = defaultdict(list)
                for g in branch_forms:
                    if set(g.branches) - concept == set(others):
                        alone[g.name].append(g.lines)
                here_: dict[str, list] = defaultdict(list)
                for g in cfs:
                    here_[g.name].append(g.lines)
                cfs = [g for g in cfs if alone.get(g.name) != here_[g.name]]
                # nor one it derives as this branch alone does, where the
                # other branch alone derives none of its name
                cfs = [g for g in cfs if g.name in alone or case_text.get(g.name) != here_[g.name]]
                if not cfs:
                    continue
                ind = "    "
                for b in others:
                    out.append(f"{ind}(ALT ${b}")
                    ind += "  "
                # the combination's forms serve the innermost alt's claims,
                # and stand in its first output block
                cl = self.ctor_claims(others[-1])
                home = next((x for x in cl if x[0] == "OUTPUT"), cl[0] if cl else None)
                tail_cfs = [g for g in cfs if g.name in tail_names | {"&out"}]
                if home is not None and len(tail_cfs) < len(cfs):
                    out.append(f"{ind}({home[0]} {home[1]} {quote(home[2])}")
                    out.extend(render_forms(topo([g for g in cfs if g.name not in tail_names | {"&out"}]), ind + "  "))
                    close(out, ")")
                    cfs = tail_cfs
                out.extend(render_forms(topo(cfs), ind))
                close(out, ")" * len(others))
            # the points that exist only with this branch
            for f2, adt2 in self.c.point_fields():
                a2 = self.ancestors(f2)
                if a2 and a2[0] == (fname, k.name):
                    sub_lines = self.render_choice(f2, adt2, *self.render_args, inherited=case_text)
                    out.extend("    " + l if l else l for l in sub_lines if l)
            close(out, ")")
        close(out, ")")
        out.append("")
        return out

    def alt_case(self, alts: list[tuple[str, str]], branch_forms, concept, main, main_text, out: list[str]
                 ) -> tuple[list["Form"], dict[str, list]]:
        """The forms of the case that takes each (point, constructor) of
        `alts`, where they differ from `main_text`, and each relation's lines
        as that case derives them."""
        adts = dict(self.c.point_fields())
        field_of = {kk.name: f_ for f_, a_ in adts.items() for kk in a_.constructors}
        pts = {f_ for f_, _ in alts}
        ks = {k for _, k in alts}
        anc = list(dict.fromkeys(a for f_, _ in alts for a in self.ancestors(f_)))
        anc_ctors = {ck for _, ck in anc}
        sib = {kk.name for f_ in pts for kk in adts[f_].constructors} | anc_ctors

        def holds(f: "Form") -> bool:
            # a form names its points' constructors as alternatives, and each
            # point of the case that it names takes the case's constructor
            bs = set(f.branches)
            return bool(bs & ks) and not (bs - concept - sib) and all(
                k in bs or not bs & {kk.name for kk in adts[f_].constructors} for f_, k in alts)
        fs = [f for f in branch_forms if holds(f)]
        fs = topo(fs)
        # drop forms identical to the concept's
        all_mine = {f.name for f in fs}
        mine_text: dict[str, list] = defaultdict(list)
        for f in fs:
            mine_text[f.name].append(f.lines)
        fs = [f for f in fs if main_text.get(f.name) != mine_text[f.name]]
        mine = all_mine | {f.name for f in branch_forms if set(f.branches) & ks}
        # what a point this one stands under derives, its alt's case derives
        mine |= {f.name for f in branch_forms if set(f.branches) - concept
                 and set(f.branches) - concept <= anc_ctors}

        def fixed(f: "Form") -> bool:
            return any(b in concept and field_of.get(b) in pts for b in f.branches)
        fixed_names = defaultdict(list)
        for f in main:
            fixed_names[f.name].append(fixed(f))
        # a determination runs once, under the concept's case, so a
        # relation it derives holds in every branch
        empty = {f.name for f in main
                 if all(fixed_names[f.name]) and f.name not in mine and f.side != "DET" and fixed(f)}
        at = dict(anc) | dict(alts)
        for name, rows in self.case_set_rows.items():
            # a set whose values hold no value of a point holds in the
            # alt's case as it holds in the concept's
            if not any(all(row.get(f_, ck) == ck for f_, ck in at.items())
                       and all(row.get(f_, v) == v for f_, v in self.concept_of.items() if f_ not in at)
                       for row in rows):
                empty.add("%" + name)
        # a concept clause whose head fixes another constructor of this
        # point, or of a point this one stands under, holds no row here
        others_k = {kk.name for f_, ck in at.items() for kk in adts[f_].constructors if kk.name != ck}
        # a concept clause that fixes no constructor of the case's points
        # holds beside the case's own clauses of its relation
        reps = getattr(self, "concept_repeats", {})
        adds = {f.name for f in fs if f.side == "RULE" and f.lines[0].startswith("(RULE ") and f.name not in reps
                and all(g.side == "RULE" and g.lines[0].startswith("(RULE ") and g.cols == f.cols
                        for g in main if g.name == f.name)}
        redo = self.dead_clauses(main, empty, mine, out, others_k, adds)
        fs = fs + redo
        reread = self.reading_determinations(fs, main)
        fs = fs + reread
        # a relation that no form of this case derives is empty in it: a
        # form of the alt that reads one is written again without it
        in_case = concept | ks | anc_ctors
        known = {f.name for f in main} | {f.name for f in branch_forms}
        fs2 = fs
        dropped_any = True
        while dropped_any:
            fs = fs2
            here_names = {f.name for f in main if not f.concept_dead} | {f.name for f in fs} | \
                {f.name for f in branch_forms if set(f.branches) <= in_case and f.name not in all_mine}
            dropped_any = False
            fs2 = []
            for f in fs:
                gone = (f.top_pos | f.top_neg | f.nested | f.reads) & (known - here_names)
                if gone and (f.src is not None or f.src_inst is not None):
                    saved = list(self.todo.pending), Counter(self.todo.kinds)
                    if f.src is not None:
                        u_, side_, scope_, sub_, ns_ = f.src
                        g = self.clause(u_, side_, scope_, sub_, ns_, drop_neg=frozenset(gone))
                    else:
                        inst_, us_, side_ = f.src_inst
                        gs_ = self.instance(inst_, us_, side_, frozenset(gone))
                        g = gs_[0] if gs_ else None
                    self.todo.pending, self.todo.kinds = saved
                    if g is None:
                        dropped_any = True
                        continue
                    g.comments, g.claim_slugs, g.branches = f.comments, f.claim_slugs, f.branches
                    fs2.append(g)
                else:
                    fs2.append(f)
        fs = fs2
        # a form written again without an empty relation can come out as the
        # concept's, and so can the clauses of a relation, merged into one
        mine_text = defaultdict(list)
        for f in fs:
            mine_text[f.name].append(f.lines)
        concept_forms: dict[str, list] = defaultdict(list)
        for f in main:
            if not f.concept_dead:
                concept_forms[f.name].append(f.concept_form or f)
        saved = Counter(MERGES), list(MERGES_UNMERGED)

        def merged(forms_) -> list:
            return [g.lines for g in merge_forms(forms_)]
        same = {n for n in mine_text if main_text.get(n) in (mine_text[n], merged([f for f in fs if f.name == n]))
                or (main_text.get(n) == [g.lines for g in concept_forms[n]]
                    and merged([f for f in fs if f.name == n]) == merged(concept_forms[n]))}
        MERGES.clear()
        MERGES.update(saved[0])
        MERGES_UNMERGED[:] = saved[1]
        same -= {f.name for f in reread}
        fs = [f for f in fs if f.name not in same]
        self.alt_derived |= {f.name for f in fs}
        # each relation as this case derives it
        case_text = defaultdict(list, main_text)
        for name in {f.name for f in fs}:
            case_text[name] = [f.lines for f in fs if f.name == name]
        beside = [f.concept_form or f for f in main if f.name in adds and not f.concept_dead]
        self.c.note_writing(fs + beside, frozenset(in_case - concept))
        return fs, case_text

