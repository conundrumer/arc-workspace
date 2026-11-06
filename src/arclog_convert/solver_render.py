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
    zero_domains,
    zero_heads,
)
from arclog_convert.terms import ctor_names

if TYPE_CHECKING:
    from arclog_convert.solver import Claim


OR_LINE = re.compile(r"\((?:RULE_OR_DET|DET_OR_RULE) ")
"""The start of a `RULE_OR_DET` or `DET_OR_RULE` line."""


def or_line(f: Form) -> bool:
    """Whether `f` is a `RULE_OR_DET` or `DET_OR_RULE` line, which is no
    clause of its relation."""
    return f.src is None and f.src_inst is None and OR_LINE.match(f.lines[0]) is not None


def holds_at(f: Form, at: dict[str, str], concept: set[str], field_of: dict[str, str]) -> bool:
    """Whether `f` holds in the case that takes the constructor `at` gives
    for each point it names, and the concept's constructor at each other
    point: each constructor of `f.branches` is the case's at its point. A
    `DET` form also holds at a constructor that is the concept's, whatever
    constructor the case takes there: Souffle's `Determine` runs once, so a
    constructor that it names in a read selects that branch's rows, which in
    the converter's cases are the concept case's. A form that also fixes a
    constructor outside the concept case is the exception for a constructor
    that its head names: the clause states the rows of that case alone."""
    alt = bool(set(f.branches) - concept)

    def holds(b: str) -> bool:
        if f.side == "DET" and b in concept and not (alt and b in f.head_branches):
            return True
        return at[field_of[b]] == b if field_of[b] in at else b in concept
    return all(holds(b) for b in f.branches)


PROPOSED = re.compile(r'\((?:DET|DET_OR_RULE|RULE_OR_DET) (&\w+)(?: "(?:[^"\\]|\\.)*")? [A-Z]')
"""The line of a relation that a proposer determines: its name, then the
proposer's, after a gloss where the line has one."""


class RenderMixin:
    """The rendering of a solver's forms, its state combinations, sinks and choices."""

    excluded_alts: list[frozenset[str]] | None = None

    # ---- placement and rendering

    def render(self, forms: list[Form], claims: list[Claim], points, concept, all_ctors) -> str:
        zero_heads(forms)
        zero_domains(forms)
        slugs = [cl.slug for cl in claims]
        idx = {s: i for i, s in enumerate(slugs)}
        # An instance form whose branches hold the concept's constructor at
        # each point it names stands in the concept with its branches cut to
        # the concept's. An instance whose inputs fix the constructors of
        # several cases stands in the concept with the inputs the concept's
        # case admits, unless the concept already holds a form of the instance.
        extra: list[Form] = []
        for f in forms:
            if f.src_inst is None or not (set(f.branches) - concept):
                continue
            inst, us, side = f.src_inst
            if any(h.src_inst is not None and h.src_inst[0] == inst and not (set(h.branches) - concept)
                   for h in forms):
                continue   # the concept has a form of the instance

            at_points: dict[str, set[str]] = defaultdict(set)
            for b in f.branches:
                at_points[all_ctors[b]].add(b)
            if all(bs & concept for bs in at_points.values()):
                # the form holds at the concept's constructor of each point it names
                extra.append(dc_replace(f, branches=tuple(sorted(set(f.branches) & concept))))
                continue

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
                g = self.settled(self.written_without(f, dr))
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
        """The text with a nested ALT for each case that combines alts of
        different points, that no exclude leaves out, that defines `&output`,
        and whose program has a form that `&output` reads at any depth, in
        text that differs from the form of that name in the deepest blocks
        the case sees: the nested ALT states each such form as the case
        derives it. This holds also where no two of the case's alts rederive
        one relation. The cases tried are the pairs of alts, and a larger
        combination only where one of its pairs got a block."""
        from arclog_convert.lint import form_reads
        from arclog_convert.lint_alts import alt_points, is_case, placements, unstated_combinations
        from arclog_convert.lint_read import L as LintL, Sym as LintSym, flat, read as lint_read
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
        point, under = alt_points(lint_read(text))

        def ancestors_of(a: str) -> set[str]:
            got, pt = set(), point[a]
            while (up := under.get(pt)) is not None:
                got.add(up)
                pt = point[up]
            return got
        cases = {frozenset()}
        for q in {frozenset({a}) | ancestors_of(a) for a in point}:
            cases |= {c | q for c in cases if is_case(c | q, point, under, excluded)}

        def chosen(case: frozenset) -> frozenset:
            """The alts of the case that are no concept constructor: those the case chooses."""
            return frozenset(a for a in case if a[1:] not in concept)
        combined = sorted((c for c in cases if len(chosen(c)) > 1), key=lambda c: (len(c), sorted(c)))
        written: set[frozenset] = set()

        def probed_case(case: frozenset) -> bool:
            """Whether the case chooses a pair of alts, or a larger combination one of whose pairs got a block."""
            return len(chosen(case)) == 2 or any(len(chosen(w)) == 2 and chosen(w) <= chosen(case) for w in written)
        probed: dict[frozenset, tuple[list[Form], list[str], Counter[str], dict, set[str]]] = {}

        def case_forms(case: frozenset) -> tuple[list[Form], list[str]]:
            """The forms of the case and the TODO lines of its program. The case
            counts its TODO kinds in `self.todo`, records its writings in the
            column map and its relations in `self.alt_derived`, only where `counted` says so, since a case that gets
            no block writes no TODO line and no forms."""
            if case not in probed:
                todo_out: list[str] = []
                had = Counter(self.todo.kinds)
                writings = {name: dict(by) for name, by in self.c.writings.items()}
                derived = set(self.alt_derived)
                fs, _ = self.alt_case([(point[a][1:], a[1:]) for a in sorted(chosen(case))], branch_forms, concept, main,
                                      main_text, todo_out)
                made = {(name, within): rec for name, by in self.c.writings.items() for within, rec in by.items()
                        if writings.get(name, {}).get(within) != rec}
                probed[case] = fs, todo_out, self.todo.kinds - had, made, self.alt_derived - derived
                self.todo.kinds = had
                self.c.writings = writings
                self.alt_derived = derived
            return probed[case][:2]

        def counted(case: frozenset) -> None:
            self.todo.kinds += probed[case][2]
            for (name, within), rec in probed[case][3].items():
                self.c.writings.setdefault(name, {})[within] = rec
            self.alt_derived |= probed[case][4]

        def deepest_text(pl, case: frozenset) -> dict[str, set[str]]:
            """The text of each form of the deepest blocks of each relation that the case sees."""
            by_name: dict[str, list] = defaultdict(list)
            for p in pl:
                if p.name and set(p.alts) <= case:
                    by_name[p.name.partition(".")[0]].append(p)
            return {name: {flat(p.form) for p in ps if len(p.alts) == max(len(q.alts) for q in ps)}
                    for name, ps in by_name.items()}

        merged: dict[tuple, set[str]] = {}

        def merged_texts(group: list[Form]) -> set[str]:
            """The text of the clauses `group` of a relation, merged as the text states them."""
            key = tuple((g.side, tuple(g.cols), tuple(g.lines), None if g.body is None else tuple(g.body),
                         repr(g.comments), tuple(g.marks)) for g in group)
            if key not in merged:
                saved = Counter(MERGES), list(MERGES_UNMERGED)
                merged[key] = {flat(lint_read("\n".join(g.lines))[0]) for g in merge_forms(group)}
                MERGES.clear()
                MERGES.update(saved[0])
                MERGES_UNMERGED[:] = saved[1]
            return merged[key]

        def stated_otherwise(name: str, texts: set[str], seen: dict[str, set[str]]) -> bool:
            return name not in seen or not texts <= seen[name]

        reads_in: dict[tuple, set[str]] = {}

        def written_reads(g: Form) -> set[str]:
            """The relations that the text of the form `g` reads, by base name: a clause
            of a case that a dead branch leaves out reads less than its `reads` give."""
            key = tuple(g.lines)
            if key not in reads_in:
                reads_in[key] = form_reads(lint_read("\n".join(g.lines))[0], g.name.partition(".")[0])
            return reads_in[key]

        def clause_heads(g: Form) -> set[str]:
            """The heads of the input clauses of the instance form `g`, which stand in its `key` clause."""
            init = lint_read("\n".join(g.lines))[0]
            return {c.head for k in init.items[3:] if isinstance(k, LintL) and k.head == "key"
                    for c in k.items[2:] if isinstance(c, LintL)}

        concept_inputs = {f.name: clause_heads(f.concept_form or f) for f in main if f.lines[0].startswith("(INIT ")}

        def whole(g: Form) -> bool:
            """Whether the form `g` is no instance with an input that the case's
            rewrite drops: an instance with an input less derives other rows
            (a `Walk` with no `succ` holds no `walk`), so the block leaves it to
            the concept's instance."""
            return g.name not in concept_inputs or concept_inputs[g.name] <= clause_heads(g)

        reads_of: dict[frozenset, dict[str, set[str]]] = {}

        def output_reads(case: frozenset) -> dict[str, set[str]]:
            """The text of each relation of the case's program that `&output` reads at any depth."""
            if case not in reads_of:
                fs, _ = case_forms(case)
                own = {g.name for g in fs}
                program: dict[str, list[Form]] = defaultdict(list)
                for g in fs + [f.concept_form or f for f in main if f.name not in own and not f.concept_dead]:
                    program[g.name].append(g)
                reached, todo = set(), ["&out"]
                while todo:
                    if (name := todo.pop()) not in reached:
                        reached.add(name)
                        todo.extend(r for g in program.get(name, ()) for r in written_reads(g))
                reads_of[case] = {n: merged_texts(program[n]) for n in sorted(reached) if n in program}
            return reads_of[case]

        otherwise: dict[frozenset, set[str]] = {}

        def read_otherwise(case: frozenset, pl) -> set[str]:
            """The relations of the case's program that `&output` reads at any depth, stated otherwise.
            The result stands until a block of alts within the case gets written."""
            if case not in otherwise:
                seen = deepest_text(pl, case)
                otherwise[case] = {n for n, texts in output_reads(case).items() if stated_otherwise(n, texts, seen)}
            return otherwise[case]

        def block_written(case: frozenset) -> None:
            written.add(case)
            for c in [c for c in otherwise if case <= c]:
                del otherwise[c]
        while True:
            forms = lint_read(text)
            pl = placements(forms)
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
            sites: dict[frozenset, set[str]] = defaultdict(set)
            for n, case, _ in unstated_combinations(pl, forms, excluded):
                if case not in done:
                    sites[case].add(n)
            for case in combined:
                if case not in done and all(a in top for a in case) and probed_case(case) \
                        and not case_forms(case)[1] and (got := read_otherwise(case, pl)):
                    sites[case] |= got
            if not sites:
                return text
            # the combinations in the order of their alts' blocks
            case = min(sites, key=lambda c: (len(c), sorted(top[a].start if a in top else -1 for a in c)))
            done.add(case)
            if not all(a in top for a in case):
                continue
            implied = set().union(*(ancestors_of(a) for a in case))
            first = min((a for a in case if a not in implied), key=lambda a: top[a].start)
            chain = sorted(case - {first} - ancestors_of(first), key=lambda a: top[a].start)
            fs, todo_out = case_forms(case)
            counted(case)
            rels = sites[case]
            new = [f for f in fs if f.name in rels]
            # a concept form reads a relation that only alts derive; the case states the form without the reads of
            # those that none of its forms derives
            made_here = {g.name for g in fs}
            new += [h for f in main if f.name in rels - made_here and not f.concept_dead
                    if (h := self.without_reads(f, set(f.dead_reads) - made_here)) is not None]
            if not new:
                continue
            # a form of the case that the new forms read, directly or through
            # other such forms, joins them where no block the case sees states
            # it, or the deepest such block states it in other text
            seen = deepest_text(pl, case)
            by_name = defaultdict(list)
            for g in fs:
                by_name[g.name].append(g)
            # the file's block of the combination states its relations: the
            # block keeps them, and the new forms are no second statement
            stated = {p.name.partition(".")[0] for p in pl if p.name and set(p.alts) == case}
            new = [g for g in new if whole(g) and g.name not in stated]
            want = set().union(*(written_reads(f) for f in new))
            reread = self.redetermined(fs, concept)
            while more := [g for g in fs if g.name in want and whole(g) and g.name not in stated
                           and (stated_otherwise(g.name, merged_texts(by_name[g.name]), seen) or g.name in reread)
                           and not any(g is h for h in new)]:
                new += more
                want |= set().union(*(written_reads(g) for g in more))
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
                block_written(case)
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
            block_written(case)

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
                lines = read_without(g.lines, f.name, drop, g.cols)
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
                lines = read_without(g.lines, f.name, drop, g.cols)
                if lines is None or lines == g.lines:
                    continue
                # the reader that reads the concept's columns holds where the points of the rederiving alts take the
                # concept's constructor, so that no case holds it beside the reader that the alts' combination states
                at_concept = {adt.constructors[0].name for _, adt in self.c.point_fields()
                              if any(k.name in bs for k in adt.constructors)} & concept
                branch_forms[branch_forms.index(g)] = dc_replace(g, lines=lines,
                                                                 branches=tuple(sorted(set(g.branches) | at_concept)))
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
                lines = read_without(base.lines, f.name, drop, r.cols)
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
                if any(f.branches for f in fs) and any(g.name == name for g in branch_forms):
                    continue   # its constructor's case states it, and an alt of that point states it again
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
        # a concept form that the branch derives again from the same Souffle
        # clause is read nowhere; a branch clause from another clause adds rows
        def derived_again(f: Form) -> bool:
            return f.name in moved and any(
                g.name == f.name and moved[f.name] == set(g.branches) - concept
                and (f.src is None or g.src is None or g.src[0] is f.src[0]) for g in branch_forms)
        main = [f for f in main if not derived_again(f)]
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
                # a case set that holds no row of the combination's case is
                # empty in it: a form that reads one is written again without
                # that read
                rowless = self.rowless_sets(dict(self.ancestors(fname)) | {fname: k.name}
                                            | {field_of[b]: b for b in others})
                cfs = [g for g in (self.without_reads(g, rowless) for g in cfs) if g is not None]
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
                # a concept clause that holds in the combination stands beside the combination's own clauses of its
                # relation; a block of these alone would hide it, so `state_combinations` states the relation
                at = dict(self.ancestors(fname)) | {fname: k.name} | {field_of[b]: b for b in others}
                beside = {f.name for f in main if f.side == "RULE" and not or_line(f) and not f.concept_dead
                          and holds_at(f, at, concept, field_of)}
                cfs = [g for g in cfs if not (g.side == "RULE" and g.name in beside)]
                if not cfs:
                    continue
                # the block of each other branch stands under the alts its
                # point stands under, so that it is deeper than that branch's
                # own block
                path: list[str] = []
                for b in others:
                    for _, up in reversed(self.ancestors(field_of[b])):
                        if up not in sib and up not in others and up not in path:
                            path.append(up)
                    path.append(b)
                ind = "    "
                for b in path:
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
                close(out, ")" * len(path))
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

    def rowless_sets(self, at: dict[str, str]) -> set[str]:
        """The case sets (`%name`) that hold no row of the case that takes
        the constructor `at` gives for each of its points: they are empty in
        it. A set whose values hold no value of a point holds in the case as
        it holds in the concept's."""
        return {"%" + name for name, rows in self.case_set_rows.items()
                if not any(all(row.get(f_, ck) == ck for f_, ck in at.items())
                           and all(row.get(f_, v) == v for f_, v in self.concept_of.items() if f_ not in at)
                           for row in rows)}

    def without_reads(self, f: "Form", gone: set[str] | frozenset[str]) -> "Form | None":
        """`f` written again without each read of `gone`, with its comments,
        claim slugs and branches; `f` itself where it reads none of them or
        has no clause to write again; `None` where nothing is left."""
        gone = frozenset((f.top_pos | f.top_neg | f.nested | f.reads) & gone)
        if not gone or (f.src is None and f.src_inst is None):
            return f
        g = self.written_without(f, gone)
        if g is not None:
            g.comments, g.claim_slugs, g.branches = f.comments, f.claim_slugs, f.branches
        return g

    def excluded_sets(self) -> list[frozenset[str]]:
        """The alts of each `exclude` line of the arcdata file that `impl_choice` gives."""
        if self.excluded_alts is None:
            saved = list(self.todo.pending), Counter(self.todo.kinds)
            excludes = self.choice_excludes(list(self.c.point_fields()))
            self.todo.pending, self.todo.kinds = saved
            self.excluded_alts = [frozenset(re.findall(r"\$\w+", m.group(1)))
                                  for x in excludes if (m := re.match(r"\(exclude \(([^)]*)\)", x))]
        return self.excluded_alts

    def alt_case(self, alts: list[tuple[str, str]], branch_forms, concept, main, main_text, out: list[str]
                 ) -> tuple[list["Form"], dict[str, list]]:
        """The forms of the case that takes each (point, constructor) of
        `alts`, and the constructor of each point they stand under, where
        they differ from `main_text`, and each relation's lines as that case
        derives them. A form holds in the case where `holds_at` says so. A
        relation the case leaves empty is one that no form of the case
        derives, or that `dead_clauses` puts in `empty` because each of its
        concept clauses holds in no case row; each form of the alt's own
        that reads one is written again without that read."""
        adts = dict(self.c.point_fields())
        field_of = {kk.name: f_ for f_, a_ in adts.items() for kk in a_.constructors}
        at = dict(a for f_, _ in alts for a in self.ancestors(f_)) | dict(alts)

        def holds(f: "Form") -> bool:
            return holds_at(f, at, concept, field_of)
        fs = topo([f for f in branch_forms if holds(f)])
        # drop forms identical to the concept's
        mine = {f.name for f in fs}
        mine_text: dict[str, list] = defaultdict(list)
        for f in fs:
            mine_text[f.name].append(f.lines)
        fs = [f for f in fs if main_text.get(f.name) != mine_text[f.name]]
        inherited = mine - {f.name for f in fs}
        clauses = [f for f in main if not or_line(f)]

        fixed_only = {f.name for f in clauses} - {f.name for f in clauses if holds(f)}
        instances = {f.name for f in main if all(g.src_inst is not None for g in main if g.name == f.name)}

        def derived_without(gone: set[str]) -> set[str]:
            # a branch form derives in the case where it holds, and keeps a
            # clause once it is written again without the relations `gone`
            return {f.name for f in branch_forms if holds(f) and self.without_reads(f, gone) is not None}
        rowless = self.rowless_sets(at)
        # a combination that an `exclude` leaves out is no case, so a relation it alone would leave empty can hold in
        # the cases that take the alts with another constructor at each other point. A relation each of whose clauses,
        # in the concept program or in a block, fixes another constructor at a point the alts fix is empty there too
        chosen = {"$" + k for k in at.values()} | {"$" + k for k in concept if field_of.get(k) not in at}
        no_case = any(x <= chosen for x in self.excluded_sets())

        def ruled_out(name: str) -> bool:
            return all(any(field_of[b] in at and at[field_of[b]] != b for b in f.branches)
                       for f in [*clauses, *branch_forms] if f.name == name)
        may_be_empty = {name for name in fixed_only if ruled_out(name)} if no_case else fixed_only
        empty = (may_be_empty - derived_without(rowless)) | rowless
        # a concept clause that holds in the case holds beside the case's own
        # clauses of its relation
        reps = getattr(self, "concept_repeats", {})
        adds = {f.name for f in fs if f.side == "RULE" and f.lines[0].startswith("(RULE ") and f.name not in reps
                and all(g.side == "RULE" and g.lines[0].startswith("(RULE ") and g.cols == f.cols
                        for g in clauses if g.name == f.name)}

        def again(g: "Form") -> bool:
            # a concept clause that the case's own form derives again from
            # the same Souffle clause holds no row beside it
            return g.src is not None and any(
                f.name == g.name and f.src is not None and f.src[0] is g.src[0] for f in fs)
        while True:
            redo = self.dead_clauses(main, empty, mine, holds, adds, again)
            # an instance whose branch forms all read a relation that
            # `dead_clauses` put in `empty` is empty too
            lapsed = (fixed_only & instances) - empty - derived_without(empty)
            if not lapsed:
                break
            empty |= lapsed
            mine -= lapsed
        if "&out" in empty:
            out.append("    ;; TODO alt-undefined: every &output clause reads a relation this alt leaves empty")
            self.todo.kinds["alt-undefined"] += 1
        fs = fs + redo
        reread = self.reading_determinations(fs, main)
        fs = fs + reread
        # a relation that no form of this case derives is empty in it, and so
        # is each that `dead_clauses` put in `empty`: a form of the alt that
        # reads one is written again without it
        known = {f.name for f in main} | {f.name for f in branch_forms}
        fs2 = fs
        dropped_any = True
        while dropped_any:
            fs = fs2
            here_names = {f.name for f in main if not f.concept_dead} | {f.name for f in fs} | inherited
            here_names -= empty
            dropped_any = False
            fs2 = []
            for f in fs:
                g = self.without_reads(f, known - here_names)
                if g is None:
                    dropped_any = True
                else:
                    fs2.append(g)
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
        beside = [f.concept_form or f for f in main if f.name in adds and not f.concept_dead and not again(f)]
        self.c.note_writing(fs + beside, frozenset(at.values()) - concept)
        return fs, case_text

