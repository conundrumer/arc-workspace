"""The lines of lint findings and hints: each finding's message, from its
payload, and its line."""

from collections.abc import Callable

from checker.finding import (
    LINT_SHAPES,
    Finding,
    LintBranchForm,
    LintCaseValue,
    LintCode,
    LintCounted,
    LintFamily,
    LintFragment,
    LintIgnore,
    LintLabeled,
    LintMarked,
    LintNamed,
    LintPayload,
    LintRun,
    LintSentence,
)
from checker.lint.recursion import RECURSIVE_INPUTS
from checker.render.faults import parse_failure_text
from checker.render.locations import LineForm, line_text, where_text
from checker.render.no_result import failure_text
from checker.render.values import _codes, _ticked
from controlled_markdown import mctx
from engine import CpuLimit, Engine, ParseFailure, WallLimit, checkout
from solver import names
from solver.aggregate import Solver
from solver.annotations import (
    HEADER_RANK,
    REVIEW_WORD,
    SIBLING_DROPS,
    CaseMarker,
    MarkerPart,
    at_word,
    header_word_text,
    ignore_text,
    marker_line,
)
from solver.category import HINTS
from solver.model import Case

FORM_RULE = "`// @rule <slug>: <text>`"
FORM_CLAIM = "`// @claim <slug> [<slug> ...]`"
HEADER_ORDER = ", ".join([*(header_word_text(w) for w in HEADER_RANK),
                          REVIEW_WORD])
"""The header lines' order, as the header-order sentence states it."""
SIBLING_DROPS_TEXT = ", ".join(f"`{header_word_text(w)}:`"
                               for w in HEADER_RANK if w in SIBLING_DROPS)
"""The fields a sibling leaves out, as the sibling sentence names them."""

TYPED_ORDER = mctx("`{0}` {how} `{1}`, a `{2}`, which has no order; store "
                   "the order as a parameter")
"""The sentence of a `typed-order` finding: the operator, aggregate or
lib relation `{0}` that orders, `{how}` the verb of its ordering, the
variable `{1}` and its type `{2}`."""

_RECURSIVE_INPUTS_CLAUSE = " or ".join(
    f"the {_ticked(sorted(inputs))} inputs of a `{name}` instance"
    for name, inputs in sorted(RECURSIVE_INPUTS.items()))

LINT_TEXT: dict[LintSentence, Callable[[tuple[str, ...], tuple[str, ...]],
                                       str]] = {
    LintSentence.RESERVED_WORD: lambda n, _: mctx(
        "`{0}` is a Souffle reserved word; rename it").format(*n),
    LintSentence.ENUMERATOR_NAME: lambda n, _: mctx(
        "`{0}` enumerates the `Choice` field type `{1}`; name it "
        "`{2}`").format(*n),
    LintSentence.SHADOWED_TYPE: lambda n, _: mctx(
        "`{0}` is also a type name inside `{1}`; rename it").format(*n),
    LintSentence.LIB_NAME: lambda n, _: mctx(
        "`{0}` is a lib {1}; rename it").format(*n),
    LintSentence.LIB_PRIVATE: lambda n, _: mctx(
        "`{0}` is private to {1}; read one of its public relations"
    ).format(*n),
    LintSentence.LIB_INTERNAL_COMP: lambda n, _: mctx(
        "`{0}` is internal to the lib; instantiate a public component"
    ).format(*n),
    LintSentence.NO_PROPOSAL_ENTRY: lambda n, _: mctx(
        "`{0}` is a proposal comp with no entry {entry}; report the "
        "operation, or fold the comp into the program").format(
            *n, entry=checkout.proposal_entry(n[0]).relative_to(
                checkout.ROOT).as_posix()),
    LintSentence.PROPOSAL_UNREAD: lambda n, _: (mctx(
        "`{comp}` is a proposal comp, and the concept case reads none of "
        "its relations; the cases that read them: {cases} "
        "([In the pass](docs/handbook/lib-protocol.md#in-the-pass))").format(
            comp=n[0], cases=_ticked(n[1:])) if n[1:] else mctx(
        "`{comp}` is a proposal comp, and no case reads its relations "
        "([In the pass]"
        "(docs/handbook/lib-protocol.md#in-the-pass))").format(comp=n[0])),
    LintSentence.PARSE_UNREAD: lambda n, _: mctx(
        "no Determine comp reads this Parse comp; read it in Determine, or "
        "fold it into the program"),
    LintSentence.MARKER_SLASH: lambda n, _: mctx(
        "the marker separates its cases with `/`; see the case markers in "
        "[Cases](docs/handbook/solver-file.md#cases)"),
    LintSentence.NO_TASK_ID: lambda n, _: mctx(
        "the file does not open with `// <task_id>`"),
    LintSentence.HEADER_ORDER: lambda n, _: mctx(
        "header lines go in the order {order}").format(order=HEADER_ORDER),
    LintSentence.HEADER_PROSE: lambda n, _: mctx(
        "no prose in the header; a remark about a case goes at its "
        "constructor, and a remark about a clause at the clause"),
    LintSentence.DRAFT_PLACE: lambda n, _: mctx(
        "`@draft` goes under the task id"),
    LintSentence.REVIEW_KIND: lambda n, _: mctx(
        "`review` takes a kind: `// review <kind>: <text>`"),
    LintSentence.FIELD_TWICE: lambda n, _: mctx(
        "`{0}` stands once in the header").format(*n),
    LintSentence.SIBLING_DROPS: lambda n, _: mctx(
        "a sibling carries `@representative:` in place of {drops}").format(
        drops=SIBLING_DROPS_TEXT),
    LintSentence.SLUG_TWICE: lambda n, _: mctx(
        "`{0}` repeats the slug of an earlier claim; a slug stands once "
        "across `@scene` and `@rule`").format(*n),
    LintSentence.UNKNOWN_KEYWORD: lambda n, _: mctx(
        "`{0}` is not in keywords.md; propose it in the review").format(*n),
    LintSentence.NO_KEYWORDS: lambda n, _: mctx(
        "the header carries `@keywords:` or `@representative:`"),
    LintSentence.NO_DEMONSTRATED_CHOICE: lambda n, _: mctx(
        "the `@keywords:` line carries `induce`, and the solver declares no "
        "`DemonstratedChoice` at the top level; add the case "
        "[Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice) "
        "gives, or remove `induce` from `@keywords:` and raise the matter in "
        "the review"),
    LintSentence.NO_RULE: lambda n, _: mctx(
        "the header has no `@rule` line; a rule is {form}").format(
        form=FORM_RULE),
    LintSentence.GLOSS_ABOVE: lambda n, _: mctx(
        "a gloss stands above `{0}`: what the choice is").format(*n),
    LintSentence.OWN_LINE: lambda n, _: mctx(
        "`{0}` opens its own line").format(*n),
    LintSentence.CONCEPT_WITNESS: lambda n, _: mctx(
        "`{0}` is the concept branch; drop its `@witness` line").format(*n),
    LintSentence.WITNESS_PLACE: lambda n, _: mctx(
        "a witness line stands in a branch's comment block or under "
        "`@approximated:`"),
    LintSentence.UNREAD_FIELD: lambda n, _: mctx(
        "case `{0}` never reads field `{1}`, so the choice point `{1}` "
        "encodes stands under the other branches").format(*n),
    LintSentence.CASE_COLUMN_FACT: lambda n, _: mctx(
        "the fact's case column holds `{0}`, and the fact stands outside "
        "the marker of that case; see "
        "[Params](docs/handbook/solver-file.md#params)").format(*n),
    LintSentence.BRANCH_APPROXIMATED: lambda n, _: mctx(
        "`@{0} {1}` stands in a branch and carries `@approximated:`; a "
        "branch's `@rule` states the rule it runs").format(*n),
    LintSentence.CLAIM_UNSTATED: lambda n, _: mctx(
        "`{0}` denotes no claim in the header").format(*n),
    LintSentence.INSTANCE_UNCLAIMED: lambda n, _: mctx(
        "`{name}` carries no `@claim` line; the claims the instance serves "
        "stand above it as {form}").format(name=n[0], form=FORM_CLAIM),
    LintSentence.CONCEPT_UNCLAIMED: lambda n, _: mctx(
        "`{name}` is the concept branch; the claim the choice answers "
        "stands above it as {form}").format(name=n[0], form=FORM_CLAIM),
    LintSentence.OPEN_VALUE_NO_RELATION: lambda n, _: mctx(
        "the `OpenValue` field `{0}` has the name of no `@open` relation; "
        "see [Cases](docs/handbook/solver-file.md#cases)").format(*n),
    LintSentence.OPEN_VALUE_NO_RECORD: lambda n, _: mctx(
        "the `OpenValue` field `{0}` is of `{1}`, which is no record the "
        "solver declares; see [Cases](docs/handbook/solver-file.md#cases)"
        ).format(*n),
    LintSentence.OPEN_VALUE_NO_COLUMN: lambda n, m: mctx(
        "`{0}`, the record of the `OpenValue` field `{1}`, names {missing}, "
        "which `{1}` has no column of; see "
        "[Cases](docs/handbook/solver-file.md#cases)").format(
            *n, missing=", ".join(f"`{x}`" for x in m)),
    LintSentence.BANNED_TYPE: lambda n, _: mctx(
        "`{0}` is none of the types "
        "[Types](docs/handbook/solver-file.md#types) lists; re-encode it or "
        "propose it").format(*n),
    LintSentence.DEAD: lambda n, _: mctx("`{0}` has no uses").format(*n),
    LintSentence.CHOICE_DOMAIN: lambda n, m: mctx(
        "`{name}` keeps one arbitrary tuple per `{over}`; state what picks "
        "it").format(name=n[0], over=", ".join(m)),
    LintSentence.RAW_AGGREGATE: lambda n, _: mctx(
        "`{0}` in the program; read it through a lib component").format(*n),
    LintSentence.RECURSION: lambda n, _: mctx(
        "the clauses of {rels} close a cycle; a closure is an instance of "
        "a lib construction, and only {inputs} "
        "may read its relations, through an atom whose every variable "
        "another atom of the clause grounds; see "
        "[Bans](docs/handbook/style.md#bans)").format(
        rels=_ticked(n), inputs=_RECURSIVE_INPUTS_CLAUSE),
    LintSentence.PASS_THROUGH: lambda n, _: mctx(
        "`{0}` only feeds `{1}`").format(*n),
    LintSentence.CHAIN_JOIN: lambda n, _: mctx(
        "`{0}.{1}` only joins `{2}`").format(*n),
    LintSentence.ARGMAX: lambda n, _: mctx(
        "`{0}` is max/min via self-join; read it through a lib component"
    ).format(*n),
    LintSentence.CONST_PRODUCT: lambda n, _: mctx(
        "{rels} share no variable; one Params relation over their columns "
        "replaces them").format(rels=_ticked(n)),
    LintSentence.CONST_JOIN: lambda n, m: mctx(
        "{rels} join on `{vars}`; name the derived constant in Params"
    ).format(rels=_ticked(n), vars=", ".join(m)),
    LintSentence.HEAD_ZERO: lambda n, m: mctx(
        "`{rel}` states {zeros} in its head; derive each zero from the "
        "relation that measures it, or drop its column").format(
        rel=n[0], zeros=_ticked(m)),
    LintSentence.HEAD_REPEAT: lambda n, m: mctx(
        "`{rel}` states {vars} in two columns; drop one of them").format(
        rel=n[0], vars=_ticked(m)),
    LintSentence.TYPED_ORDER_COMPARES: lambda n, _: TYPED_ORDER.format(
        *n, how=mctx("compares")),
    LintSentence.TYPED_ORDER_ORDERS: lambda n, _: TYPED_ORDER.format(
        *n, how=mctx("orders")),
    LintSentence.TYPED_ORDER_RANKS: lambda n, _: TYPED_ORDER.format(
        *n, how=mctx("ranks")),
}
"""The sentence of each `LintNamed` finding, from its names and its
second list."""

COUNTED_TEXT: dict[LintSentence, Callable[[LintCounted], str]] = {
    LintSentence.LONG_CLAUSE: lambda p: mctx(
        "{width} > {limit} chars of code on one line; wrap the body").format(
        width=p.count, limit=p.other),
    LintSentence.SINGLE_CONSUMER: lambda p: mctx(
        "`{name}` has one clause and one use ({line})").format(
        name=p.names[0], line=line_text(p.other)),
    LintSentence.COMMON_SUBEXPR: lambda p: mctx(
        "{width} literals shared with `{name}` ({line})").format(
        width=p.count, name=p.names[0], line=line_text(p.other)),
    LintSentence.COMMON_SUBEXPR_MERGE: lambda p: mctx(
        "{width} literals shared with `{name}` ({line}); merge the "
        "tails into a disjunction").format(
        width=p.count, name=p.names[0], line=line_text(p.other)),
}
"""The sentence of each `LintCounted` finding."""

CODE_TEXT: dict[LintSentence, Callable[[Engine, LintCode], str]] = {
    LintSentence.ALIAS: lambda e, p: mctx(
        "`{head}` is `{atom}` renamed").format(
        head=e.text(p.code[0]), atom=e.text(p.code[1])),
    LintSentence.NEGATED_USE: lambda e, p: mctx(
        "`{code}` ⇒ `{parts}`").format(
        code=_codes(e, p.code), parts=_codes(e, p.rewritten)),
    LintSentence.CHOICE_TAG: lambda e, p: mctx(
        "same body under `{one}` and `{other}`; one clause takes the tag as a "
        "variable that a relation holding both tags binds, with each other "
        "tag it holds excluded; see "
        "[Choice grounding via `impl_choice`]"
        "(docs/handbook/patterns.md#choice-grounding-via-impl_choice)"
        ).format(one=e.text(p.code[0]), other=e.text(p.code[1])),
    LintSentence.CROSS_CHOICE: lambda e, p: mctx(
        "branches bind {tags}; see "
        "[Disjunction](docs/handbook/style.md#disjunction)").format(
        tags=", ".join(f"`{e.text(c)}`" for c in p.code)),
    LintSentence.ATOM_TWICE: lambda e, p: mctx(
        "`{atom}` appears twice in the body").format(atom=e.text(p.code[0])),
    LintSentence.ATOM_ADDS_NOTHING: lambda e, p: mctx(
        "`{atom}` adds nothing next to `{other}`").format(
        atom=e.text(p.code[0]), other=e.text(p.code[1])),
    LintSentence.NEGATED_VALUE: lambda e, p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(e, p.code), rewritten=_codes(e, p.rewritten)),
    LintSentence.NAMED_COMPLEMENT: lambda e, p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(e, p.code), rewritten=_codes(e, p.rewritten)),
    LintSentence.LIB_IDIOM: lambda e, p: mctx(
        "`{code}` ⇒ `{rewritten}`").format(
        code=_codes(e, p.code), rewritten=_codes(e, p.rewritten)),
    LintSentence.COMP_IDIOM_MEMBER: lambda e, p: mctx(
        "`{code}` states the other member of a two-member type; write "
        "`{rewritten}`").format(code=_codes(e, p.code),
                                rewritten=_codes(e, p.rewritten)),
    LintSentence.COMP_IDIOM_IMAGE: lambda e, p: mctx(
        "`{code}` through `{link}` is `{comp}`").format(
        code=_codes(e, p.code), link=p.names[0], comp=p.names[1]),
    LintSentence.DOMAIN_ENUMERATOR: lambda e, p: mctx(
        "`{atom}`; `{var}` is already bound by `{binder}`").format(
        atom=e.text(p.code[0]), var=e.text(p.code[1]),
        binder=p.names[0]),
}
"""The sentence of each `LintCode` finding."""

def part_text(part: MarkerPart) -> str:
    """One name of a case marker as the marker writes it."""
    return part.name


def marker_text(m: CaseMarker) -> str:
    """A case marker's text between its dashes."""
    parts = ", ".join(part_text(p) for p in m.parts)
    return parts + (f": {m.gloss}" if m.gloss else "")


def _marked_text(engine: Engine, p: LintMarked) -> str:
    match p.sentence:
        case LintSentence.SHARED_UNREAD:
            return mctx("`{name}` is shared, and the cases {cases} never "
                        "read it; move it under the marker of the cases "
                        "that read it").format(name=p.name,
                                               cases=_ticked(p.cases))
        case LintSentence.SHARED_UNREAD_BY_ONE:
            return mctx("`{name}` is shared, and the case {case} never "
                        "reads it; move it under the marker of the cases "
                        "that read it").format(name=p.name,
                                               case=_ticked(p.cases))
        case LintSentence.SHARED_NO_READER:
            return mctx("`{name}` is shared, and no case reads it").format(
                name=p.name)
        case LintSentence.CASE_SECTION_READ:
            return mctx("by the program's rules, not by a run, {cases} "
                        "read `{rel}`, which the clause feeds, and the "
                        "marker `{marker}` above it does not list them; see "
                        "\"Case markers\" in "
                        "[Cases](docs/handbook/solver-file.md#cases)").format(
                cases=_ticked(p.cases), rel=p.name,
                marker=_marker_line(engine, p.marker))
        case LintSentence.SHARED_FACT_MARKED:
            return mctx("`{name}` is declared above the case markers and "
                        "has no case column, and this fact of it stands "
                        "under `{marker}`; move the fact to its "
                        "declaration").format(
                name=p.name, marker=_marker_line(engine, p.marker))
        case LintSentence.MARKER_LISTS_NO_CASE:
            return mctx("`{name}` is under the marker `{marker}`, which "
                        "lists no case; see "
                        "[Cases](docs/handbook/solver-file.md#cases)").format(
                name=p.name, marker=_marker_or_none(p.marker))
        case LintSentence.DECL_PLACEMENT:
            spot = p.comp if p.comp is not None else \
                _marker_or_none(p.marker)
            return mctx("all uses of `{name}` are in {spot}").format(
                name=p.name, spot=spot)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _marker_or_none(m: CaseMarker | None) -> str:
    if m is None:
        raise ValueError("a marked lint finding without its marker")
    return marker_text(m)


def _marker_line(engine: Engine, m: CaseMarker | None) -> str:
    """A marked lint finding's marker as its comment line
    (`solver.annotations.marker_line`)."""
    return marker_line(engine, _marker_or_none(m))


def _case_value_text(engine: Engine, p: LintCaseValue) -> str:
    values = (mctx("the case value {values}") if len(p.values) == 1
              else mctx("the case values {values}")).format(
        values=_ticked([engine.text(v) for v in p.values]))
    match p.sentence:
        case LintSentence.CASE_SECTION_BEFORE:
            return mctx("the clause contains {values} and stands before the "
                        "first marker").format(values=values)
        case LintSentence.CASE_SECTION_UNDER:
            return mctx("the clause contains {values} and stands under "
                        "`{marker}`").format(
                values=values, marker=_marker_line(engine, p.marker))
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _labeled_text(p: LintLabeled) -> str:
    if p.sentence != LintSentence.ORDINARY_RELAXED:
        raise ValueError(f"no sentence for {p.sentence}")
    what = at_word(p.word) + (f" {p.name}" if p.name is not None else "")
    return mctx("`{what}` is `ordinary` and carries {relaxed}; see "
                "plausibility in "
                "[Witnesses](docs/handbook/principles.md#witnesses)").format(
        what=what, relaxed=", ".join(f"`@relaxed {s}`" for s in p.relaxed))


def _run_text(solver: Solver, p: LintRun) -> str:
    match p.sentence, p.outcome:
        case LintSentence.ONE_CASE_UNKNOWN_TIMEOUT, CpuLimit(seconds=t) \
                | WallLimit(seconds=t):
            return mctx("the run that gives the solver's cases "
                        "timed out after {seconds}s, so whether it has one "
                        "case is unknown").format(seconds=f"{t:g}")
        case LintSentence.ONE_CASE_UNKNOWN_FAILED, Case():
            raise ValueError("a failed run of the solver's cases without its failure")
        case LintSentence.ONE_CASE_UNKNOWN_FAILED, failure:
            return mctx("the run that gives the solver's cases "
                        "fails, so whether it has one case is unknown: "
                        "{failure}").format(failure=failure_text(failure))
        case LintSentence.CASE_SECTION_UNJUDGED, Case():
            raise ValueError("an unjudged case section without its failure")
        case LintSentence.CASE_SECTION_UNJUDGED, failure:
            return mctx("the run that gives the solver's cases gave "
                        "no result, so no clause under a case marker was "
                        "judged against the cases its marker lists: "
                        "{failure}").format(failure=failure_text(failure))
        case LintSentence.CASE_SECTION_READ_UNJUDGED, Case():
            raise ValueError("an unjudged case section without its failure")
        case LintSentence.CASE_SECTION_READ_UNJUDGED, failure:
            return mctx("the run that gives the solver's cases gave "
                        "no result, so no marker was judged against the "
                        "cases that read its clauses: {failure}").format(
                failure=failure_text(failure))
        case LintSentence.ONE_CASE, Case() as case:
            return mctx("the solver has one case, `{case}`, and "
                        "declares `Choice`; see "
                        "[Cases](docs/handbook/solver-file.md#cases)").format(
                case=names.name(solver, case))
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _family_text(p: LintFamily) -> str:
    match p.sentence, p.failure:
        case LintSentence.FAMILY_NOT_PARSED, ParseFailure() as failure:
            return mctx("`{task}` does not parse ({error}), so `{case}` "
                        "cannot be checked against its `Choice`").format(
                task=p.task_id, case=p.case, error=parse_failure_text(failure))
        case LintSentence.FAMILY_RECORD, None:
            return mctx("`{task}`'s `Choice` is a record, so the line takes "
                        "no case").format(task=p.task_id)
        case LintSentence.FAMILY_NO_CASE, None:
            return mctx("`{case}` is no case of `{task}`'s `Choice`; give a "
                        "case the representative holds").format(
                task=p.task_id, case=p.case)
        case LintSentence.FAMILY_NO_CHOICE, None:
            return mctx("`{task}` declares no `Choice`, so the line takes "
                        "no case").format(task=p.task_id)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def _ignore_text(p: LintIgnore) -> str:
    ig = p.ignore
    if ig.category is None:
        raise ValueError("an `@ignore` line of the lint form has a category")
    category = ig.category.value
    match p.sentence:
        case LintSentence.IDLE_IGNORE:
            if p.site is None:
                raise ValueError("an idle `@ignore` line stands on a site")
            site = p.site.text
            return mctx("no finding or hint with the category `{category}` "
                        "fires on `{site}`").format(category=category,
                                                   site=site)
        case LintSentence.IGNORE_ON_LINT:
            return mctx("`{category}` gives a lint finding, which an "
                        "`@ignore` line does not dismiss").format(category=category)
        case LintSentence.IGNORE_ON_DECL | LintSentence.IGNORE_UNPLACED:
            directive = ignore_text(ig.relation, ig.category)
            if p.sentence == LintSentence.IGNORE_ON_DECL:
                return mctx("`{d}` states a relation above a `.decl`"
                            ).format(d=directive)
            return mctx("`{d}` stands in no run of `@ignore` lines "
                        "directly above a `.decl` or `.init`"
                        ).format(d=directive)
        case _:
            raise ValueError(f"no sentence for {p.sentence}")


def lint_message(solver: Solver, p: LintPayload) -> str:
    """A lint finding's message, the part after its category."""
    match p:
        case LintFragment(fragment=fragment):
            return f"`{fragment}`"
        case LintNamed(sentence=s, names=names, more=more):
            return LINT_TEXT[s](names, more)
        case LintCounted(sentence=s):
            return COUNTED_TEXT[s](p)
        case LintCode(sentence=s):
            return CODE_TEXT[s](solver.engine, p)
        case LintMarked():
            return _marked_text(solver.engine, p)
        case LintCaseValue():
            return _case_value_text(solver.engine, p)
        case LintLabeled():
            return _labeled_text(p)
        case LintRun():
            return _run_text(solver, p)
        case LintFamily():
            return _family_text(p)
        case LintIgnore():
            return _ignore_text(p)
        case LintBranchForm(finding=inner, relations=rels, cases=cases):
            return lint_message(solver, inner) + mctx(
                "; no derivation of the concept case reads {rels}, and the "
                "cases that read {them}: {cases}; a branch whose claim needs "
                "this form fails [Relational form]"
                "(docs/handbook/principles.md#relational-form)").format(
                rels=_ticked([r.text for r in rels]),
                them="it" if len(rels) == 1 else "them",
                cases=_ticked(cases))


def lint_line(solver: Solver, f: Finding) -> str:
    """One lint finding or hint as a line: where, the category an `@ignore`
    line takes, and the message; on a hint that stands on a relation, the
    directive that keeps it
    ([Program](docs/handbook/solver-file.md#program))."""
    p = f.payload
    assert isinstance(p, LINT_SHAPES)
    line = f"{where_text(solver, f.where, LineForm.FILE)}: " \
           f"{p.category.value}: " \
           f"{lint_message(solver, p)}"
    if p.category in HINTS and p.on_relation:
        line += mctx("; an `@ignore` directive can keep the relation it "
                     "fires on")
    return line
