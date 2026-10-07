"""The commands that survey a solver without judging a witness: `sweep`,
`deletions`, `drop-one`, `derived-constant`, `determination-plan`,
`size`, `keywords`, `since` and `expand`."""

import re
import sys
from collections import defaultdict

from checker import Runs
from checker.deletions import DeletionReport, survey_deletions
from checker.derived_constant import survey_derived_constant
from checker.determination_plan import survey_determination_plan
from checker.drop_one import survey_drop_one
from checker.judged import parse_failure
from checker.lint.form.header import (
    doc_keywords,
    header_keywords,
    keywords_doc,
    known_keywords,
)
from checker.render import header_line, keywords
from checker.render.surveys import (
    render_deletions,
    render_derived_constant,
    render_determination_plan,
    render_drop_one,
    render_sweep,
)
from checker.sweep import MAX_CANDIDATES, TIME_LIMIT_SECONDS, survey_sweep
from cli import text
from cli.common import (
    LIMITS,
    all_stems,
    command_solver,
    compiles,
    engine,
    missing,
    stem_of,
)
from engine import Program, checkout
from engine.program import (
    AtomLiteral,
    BodyLiteral,
    BoolLiteral,
    Comparison,
    Disjunction,
    GridCall,
    literal_aggregates,
    own,
)
from solver.load import load
from solver.aggregate import Solver
from souffle import SouffleEngine

# The surveys


def _runs(arg: str, task: bool = False) -> Runs | None:
    """The runs of the solver the argument names; None, with its line on
    stderr, where no solver file stands there, or, under `task`, where its
    task has no task file."""
    eng = engine()
    solver = command_solver(arg, eng, task=task)
    return None if solver is None else Runs(eng, solver, LIMITS)


def cmd_sweep(arg: str, cap: int = MAX_CANDIDATES,
              sweep_limit: float = TIME_LIMIT_SECONDS) -> int:
    runs = _runs(arg, task=True)
    if runs is None:
        return 2
    report = survey_sweep(runs.solver, runs, cap, sweep_limit)
    print("\n".join(render_sweep(runs.solver, report)))
    return 0


def cmd_deletions(arg: str) -> int:
    runs = _runs(arg)
    if runs is None:
        return 2
    result = survey_deletions(runs.solver, runs)
    print("\n".join(render_deletions(runs.solver, result)))
    return 0 if isinstance(result, DeletionReport) else 1


def cmd_drop_one(arg: str) -> int:
    runs = _runs(arg)
    if runs is None:
        return 2
    print("\n".join(render_drop_one(runs.solver,
                                    survey_drop_one(runs.solver, runs))))
    return 0


def cmd_derived_constant(arg: str) -> int:
    eng = engine()
    solver = command_solver(arg, eng)
    if solver is None:
        return 2
    if not compiles(eng, solver):
        return 1
    runs = Runs(eng, solver, LIMITS)
    print("\n".join(render_derived_constant(
        runs.solver, survey_derived_constant(runs.solver, runs))))
    return 0


def cmd_determination_plan(arg: str, verdicts: bool = False) -> int:
    runs = _runs(arg, task=True)
    if runs is None:
        return 2
    print("\n".join(render_determination_plan(
        runs.solver, survey_determination_plan(runs.solver, runs),
        verdicts)))
    return 0


# `size`


def _parsed(stem: str, eng: SouffleEngine) -> Solver | None:
    """The solver of `stem`; None, with what the parser reported on
    stderr, where it does not parse (`checker.judged.parse_failure`)."""
    solver = load(stem, eng)
    failure = parse_failure(solver)
    if failure is None:
        return solver
    print(keywords.size_unread(stem, failure), file=sys.stderr)
    return None


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
            return 1 + sum(_literals(x) for a in literal_aggregates(lit)
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
        solver = _parsed(stem, eng)
        if solver is None:
            bad = True
            continue
        print(keywords.SIZE_ROW.format(count=literal_count(solver.program),
                                       stem=stem))
    return 1 if bad else 0


# `keywords`

def cmd_keywords(args: list[str] | None = None) -> int:
    """How many solvers carry each keyword of keywords.md, and each header
    keyword the doc does not list."""
    for a in args or []:
        if missing(a):
            return 2
    eng = engine()
    stems = [stem_of(a) for a in args] if args else all_stems()
    sections = doc_keywords(keywords_doc().read_text())
    known = known_keywords()
    carriers: dict[str, set[str]] = defaultdict(set)
    unknown: list[str] = []
    bad = False
    for stem in stems:
        solver = _parsed(stem, eng)
        if solver is None:
            bad = True
            continue
        got = header_keywords(solver)
        words = [] if got is None else got[1]
        for word in words:
            if word in known:
                carriers[word].add(stem)
            else:
                unknown.append(keywords.UNKNOWN_KEYWORD.format(stem=stem,
                                                           word=word))
    for name, words in sections.items():
        print(header_line(name))
        for word in words:
            print(keywords.KEYWORD_ROW.format(n=len(carriers[word]), word=word))
        print()
    for line in unknown:
        print(line)
    print(keywords.UNKNOWN_KEYWORDS.format(n=len(unknown)))
    return 1 if bad else 0


# `since`

REWRITE_SHARE = 0.5
"""The share of the corpus above which commits count as a mechanical
rewrite rather than solver work."""


def _solver_stem(path: str, solvers: str) -> str | None:
    """The stem of the solver file at `path`, a path from the checkout's
    root, with `solvers` the solvers directory as git names it; None where
    `path` is no solver file."""
    m = re.fullmatch(re.escape(solvers) + r"/([^/]+)\.dl", path)
    return m.group(1) if m else None


def _commit_stems(log: str, solvers: str) -> list[tuple[str, set[str]]]:
    """Each commit as its hash and the solver stems it touches."""
    commits: list[tuple[str, set[str]]] = []
    for line in log.splitlines():
        if line.startswith("commit "):
            commits.append((line.split(" ", 1)[1].strip(), set()))
        elif (stem := _solver_stem(line.strip(), solvers)) and commits:
            commits[-1][1].add(stem)
    return commits


def _rewrite(touched: set[str], corpus: set[str]) -> bool:
    return len(touched) > REWRITE_SHARE * len(corpus)


def cmd_since(when: str) -> int:
    """The stems the commits since `when` touch, and those whose
    working-tree content differs from HEAD, the scope lib-protocol.md
    gives under "The sequence" for a survey of an entry whose newest
    `Survey:` time is `when`; a commit that rewrites more
    than half the corpus gives none, and a window whose commits together
    do keeps only the solvers they add. A git call that fails exits 1
    with git's error."""
    try:
        return _since(when)
    except checkout.GitFailed as e:
        print(text.GIT_FAILED.format(error=e.stderr.strip()), file=sys.stderr)
        return 1


def _since(when: str) -> int:
    root = checkout.ROOT
    solvers = checkout.solvers().relative_to(root).as_posix()
    log = checkout.git_out(root, "log", f"--since={when}", "--name-only",
                           "--pretty=format:commit %H", "--", solvers)
    worktree = {stem for c in checkout.changed_paths(root, "HEAD", solvers)
                if (stem := _solver_stem(c.path, solvers))}
    corpus = set(all_stems())
    committed: set[str] = set()
    for sha, touched in _commit_stems(log, solvers):
        if _rewrite(touched, corpus):
            print(keywords.SKIPPED_REWRITE.format(
                sha=sha, n=len(touched), total=len(corpus),
                share=REWRITE_SHARE), file=sys.stderr)
        else:
            committed |= touched
    if _rewrite(committed, corpus):
        added = checkout.git_out(root, "log", f"--since={when}", "--diff-filter=A",
                                 "--name-only", "--pretty=format:commit %H", "--",
                                 solvers)
        kept = committed & {s for _, t in _commit_stems(added, solvers) for s in t}
        print(keywords.WINDOW_REWRITE.format(
            n=len(committed), total=len(corpus), share=REWRITE_SHARE,
            kept=len(kept)), file=sys.stderr)
        committed = kept
    in_scope = sorted((committed | worktree) & corpus)
    for stem in in_scope:
        print(stem)
    print(keywords.IN_SCOPE.format(n=len(in_scope)), file=sys.stderr)
    return 0


# `expand`


def cmd_expand(arg: str) -> int:
    """The solver's text with each GRID call and RIGID block replaced by
    the units it states: the engine's rendering of the expanded program,
    each line that renders the solver's own text."""
    eng = engine()
    solver = command_solver(arg, eng, task=False)
    if solver is None:
        return 2
    rendered = eng.render(eng.expand(solver.program))
    sys.stdout.write("".join(f"{ln.text}\n" for ln in rendered.lines))
    return 0
