"""The commands that survey a solver without judging a witness: `sweep`,
`deletions`, `drop-one`, `derived-constant`, `determination-plan`,
`size`, `keywords`, `since` and `expand`."""

import dataclasses
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterator

from checker import Runs
from checker.deletions import DeletionReport, survey_deletions
from checker.derived_constant import survey_derived_constant
from checker.determination_plan import survey_determination_plan
from checker.drop_one import survey_drop_one
from checker.render import commands
from checker.render.surveys import (
    render_deletions,
    render_derived_constant,
    render_determination_plan,
    render_drop_one,
    render_sweep,
)
from checker.sweep import MAX_CANDIDATES, TIME_LIMIT_SECONDS, survey_sweep
from checker.lint.form import keywords_doc
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    engine,
    load_solver,
    missing,
    stem_of,
)
from engine import ParseFailure, Program, checkout
from engine.program import (
    Aggregate,
    AtomLiteral,
    BodyLiteral,
    BoolLiteral,
    Comparison,
    Disjunction,
    GridCall,
)
from solver.annotations import HeaderWord
from solver.model import Solver, load, own
from solver.problems import ProblemKind

# The surveys


def _runs(arg: str) -> tuple[Runs, int] | int:
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    return Runs(eng, solver, LIMITS), 0


def cmd_sweep(arg: str, cap: int = MAX_CANDIDATES,
              time_limit: float = TIME_LIMIT_SECONDS) -> int:
    got = _runs(arg)
    if isinstance(got, int):
        return got
    runs, _ = got
    report = survey_sweep(runs.solver, runs, cap, time_limit)
    print("\n".join(render_sweep(runs.solver, report)))
    return 0


def cmd_deletions(arg: str) -> int:
    got = _runs(arg)
    if isinstance(got, int):
        return got
    runs, _ = got
    result = survey_deletions(runs.solver, runs)
    print("\n".join(render_deletions(runs.solver, result)))
    return 0 if isinstance(result, DeletionReport) else 1


def cmd_drop_one(arg: str) -> int:
    got = _runs(arg)
    if isinstance(got, int):
        return got
    runs, _ = got
    print("\n".join(render_drop_one(runs.solver,
                                    survey_drop_one(runs.solver, runs))))
    return 0


def cmd_derived_constant(arg: str) -> int:
    got = _runs(arg)
    if isinstance(got, int):
        return got
    runs, _ = got
    print("\n".join(render_derived_constant(
        runs.solver, survey_derived_constant(runs.solver, runs))))
    return 0


def cmd_determination_plan(arg: str, verdicts: bool = False) -> int:
    got = _runs(arg)
    if isinstance(got, int):
        return got
    runs, _ = got
    print("\n".join(render_determination_plan(
        runs.solver, survey_determination_plan(runs.solver, runs),
        verdicts)))
    return 0


# `size`


def parse_failure(solver: Solver) -> ParseFailure | None:
    """What the parser reported, for a solver that does not parse."""
    return next((p.detail for p in solver.problems
                 if p.kind == ProblemKind.PARSE_FAILURE
                 and isinstance(p.detail, ParseFailure)), None)


def _aggregates(value: object) -> Iterator[Aggregate]:
    """Each aggregate inside a term, outermost first."""
    if isinstance(value, Aggregate):
        yield value
        return
    if isinstance(value, tuple):
        for v in value:
            yield from _aggregates(v)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield from _aggregates(getattr(value, f.name))


def _literals(lit: BodyLiteral) -> int:
    """A body literal's share of the size measure: one per atom, negation
    or comparison, disjunction branches expanded, and the literals of each
    aggregate body it holds."""
    match lit:
        case BoolLiteral():
            return 0
        case Disjunction(branches=branches):
            return sum(_literals(x) for b in branches for x in b)
        case AtomLiteral() | Comparison():
            return 1 + sum(_literals(x) for a in _aggregates(lit)
                           for x in a.body)


def literal_count(program: Program) -> int:
    """The size measure: per rule of the solver's own text, one for the
    head and one per body literal (`_literals`); a fact, and a GRID call,
    counts its head alone."""
    return sum(1 + sum(_literals(lit) for lit in (u.body or ()))
               for u in program.units if own(u.span)) \
        + sum(1 for m in program.macros
              if isinstance(m, GridCall) and own(m.span))


def cmd_size(arg: str | None = None) -> int:
    """The literal count of each solver, count first."""
    if arg and missing(arg):
        return 2
    eng = engine()
    bad = False
    for stem in [stem_of(arg)] if arg else all_stems():
        solver = load(stem, eng)
        failure = parse_failure(solver)
        if failure is not None:
            print(commands.size_unread(stem, failure), file=sys.stderr)
            bad = True
            continue
        print(commands.SIZE_ROW.format(count=literal_count(solver.program),
                                       stem=stem))
    return 1 if bad else 0


# `keywords`

KEYWORD_BULLET_RE = re.compile(r"^- `([^`]+)`")


def doc_keywords(written: str) -> dict[str, list[str]]:
    """The keywords of keywords.md, in doc order, per `##` section: the
    leading code span of each bullet."""
    out: dict[str, list[str]] = {}
    section: list[str] = []
    for line in written.splitlines():
        if line.startswith("## "):
            section = out.setdefault(line[3:].strip(), [])
        elif m := KEYWORD_BULLET_RE.match(line):
            section.append(m.group(1))
    return out


def cmd_keywords(args: list[str] | None = None) -> int:
    """How many solvers carry each keyword of keywords.md, and each header
    keyword the doc does not list."""
    for a in args or []:
        if missing(a):
            return 2
    eng = engine()
    stems = [stem_of(a) for a in args] if args else all_stems()
    sections = doc_keywords(keywords_doc().read_text())
    known = {w for words in sections.values() for w in words}
    carriers: dict[str, set[str]] = defaultdict(set)
    unknown: list[str] = []
    bad = False
    for stem in stems:
        solver = load(stem, eng)
        failure = parse_failure(solver)
        if failure is not None:
            print(commands.size_unread(stem, failure), file=sys.stderr)
            bad = True
            continue
        field = next((f for f in solver.annotations.header
                      if f.word == HeaderWord.KEYWORDS), None)
        words = field.value.split("\n")[0].split() if field else []
        for word in words:
            if word in known:
                carriers[word].add(stem)
            else:
                unknown.append(commands.UNKNOWN_KEYWORD.format(stem=stem,
                                                           word=word))
    for name, words in sections.items():
        print(commands.KEYWORDS_SECTION.format(name=name))
        for word in words:
            print(commands.KEYWORD_ROW.format(n=len(carriers[word]), word=word))
        print()
    for line in unknown:
        print(line)
    print(commands.UNKNOWN_KEYWORDS.format(n=len(unknown)))
    return 1 if bad else 0


# `since`

SOLVER_PATH_RE = re.compile(r"programs/solvers/([^/]+)\.dl$")
REWRITE_SHARE = 0.5
"""The share of the corpus above which commits count as a mechanical
rewrite rather than solver work."""


def _git(*args: str) -> str | None:
    """Git's stdout, or None where the call fails."""
    ran = subprocess.run(["git", *args], cwd=checkout.ROOT, capture_output=True,
                         text=True)
    return ran.stdout if ran.returncode == 0 else None


def _commit_stems(log: str) -> list[tuple[str, set[str]]]:
    """Each commit as its hash and the solver stems it touches."""
    commits: list[tuple[str, set[str]]] = []
    for line in log.splitlines():
        if line.startswith("commit "):
            commits.append((line.split(" ", 1)[1].strip(), set()))
        elif (m := SOLVER_PATH_RE.match(line.strip())) and commits:
            commits[-1][1].add(m.group(1))
    return commits


def _rewrite(touched: set[str], corpus: set[str]) -> bool:
    return len(touched) > REWRITE_SHARE * len(corpus)


def _worktree_stems(status: str) -> set[str]:
    stems: set[str] = set()
    for line in status.splitlines():
        path = line[3:].strip().split(" -> ")[-1].strip('"')
        if m := SOLVER_PATH_RE.match(path):
            stems.add(m.group(1))
    return stems


def cmd_since(when: str) -> int:
    """The stems the commits since `when` touch, and those whose
    working-tree content differs from HEAD; a commit that rewrites more
    than half the corpus gives none, and a window whose commits together
    do keeps only the solvers they add."""
    log = _git("log", f"--since={when}", "--name-only",
               "--pretty=format:commit %H", "--", "programs/solvers")
    status = _git("status", "--porcelain", "--", "programs/solvers")
    if log is None or status is None:
        print(text.NO_HISTORY.format(when=when), file=sys.stderr)
        return 1
    corpus = set(all_stems())
    committed: set[str] = set()
    for sha, touched in _commit_stems(log):
        if _rewrite(touched, corpus):
            print(commands.SKIPPED_REWRITE.format(
                sha=sha, n=len(touched), total=len(corpus),
                share=REWRITE_SHARE), file=sys.stderr)
        else:
            committed |= touched
    if _rewrite(committed, corpus):
        added = _git("log", f"--since={when}", "--diff-filter=A",
                     "--name-only", "--pretty=format:commit %H", "--",
                     "programs/solvers")
        if added is None:
            print(text.NO_HISTORY.format(when=when), file=sys.stderr)
            return 1
        kept = committed & {s for _, t in _commit_stems(added) for s in t}
        print(commands.WINDOW_REWRITE.format(
            n=len(committed), total=len(corpus), share=REWRITE_SHARE,
            kept=len(kept)), file=sys.stderr)
        committed = kept
    in_scope = sorted((committed | _worktree_stems(status)) & corpus)
    for stem in in_scope:
        print(stem)
    print(commands.IN_SCOPE.format(n=len(in_scope)), file=sys.stderr)
    return 0


# `expand`


def cmd_expand(arg: str) -> int:
    """The solver's text with each GRID call and RIGID block replaced by
    the units it states: the engine's rendering of the expanded program,
    each line that renders the solver's own text."""
    if missing(arg):
        return 2
    eng = engine()
    solver = load_solver(arg, eng)
    rendered = eng.render(eng.expand(solver.program))
    sys.stdout.write("".join(f"{ln.text}\n" for ln in rendered.lines))
    return 0
