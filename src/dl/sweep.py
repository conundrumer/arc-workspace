"""Conditional sweep of a solver's parameter values: which values the pairs admit."""

import itertools
import re
import sys
import time
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from concurrent.futures import Future, ThreadPoolExecutor

from arc.task import load as load_task
from controlled_markdown import mctx
from dl.dlparse import (
    SECTION_RE,
    ParseError,
    TypeDecl,
    marker_names,
    parse,
)
from dl.domains import (
    ENUM_TYPES,
    MAG_POSITION_TYPES,
    POSITION_TYPES,
    _color_domain,
    _enum_domain,
    _lib_defines,
    _number_domain,
    _position_domain,
)
from dl.facts import grid_to_facts, parse_output
from dl.models import BRANCH_RE, TERM_RE, Space, case_space, model_label
from dl.solve import (
    PairRun,
    _pair_profile,
    _profile,
    cases_of,
    profile_of,
    res_out,
    solver_file,
)
from dl.souffle import _pool_workers, _run_source
from dl.source import (
    RIGID_CHART_PREFIX,
    _comp_span,
    _param_facts,
    _render_arg,
    _split_args,
    build_source,
    comp_decls,
    expand_macros,
    public_param,
    shared_params,
    swap_fact,
    swap_facts,
)

# `dl.sweep_open` reads the clauses of a report back off a cached run, so
# the wording the render prints is the interface between the two.
PROGRESS = mctx("sweeping {name}: {count} candidate values")
"""The line the sweep prints to stderr as it starts one parameter."""

REFUTES = mctx("test refutes {shown} — {note}")
"""The clause on the values the test pairs refute."""

PASSING = mctx("{shown} reproduce the stored outputs on test too")
"""The clause on the values the test pairs admit as well."""

MAX_CANDIDATES = 256
TIME_LIMIT_SECONDS = 180.0


class _Clock:
    """A wall-clock limit for the solver runs of one sweep."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.start = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.start

    def spent(self) -> bool:
        return self.elapsed() >= self.seconds


def _run_candidates(test, candidates: list, clock: _Clock) -> tuple[list, int]:
    """Run `test` over the candidates in chunks until the limit is spent.

    The clock is read between chunks, so a chunk in flight finishes. The
    first chunk always runs, so a spent limit still leaves a reading of
    the parameter. Returns the rows and the number of candidates run.
    """
    chunk = _pool_workers() or 8
    rows: list = []
    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        for i in range(0, len(candidates), chunk):
            if rows and clock.spent():
                break
            rows.extend(executor.map(test, candidates[i:i + chunk]))
    return rows, len(rows)


class _TrainRuns:
    """The train runs of the stored value and of every candidate, in one
    pool: one job per stored pair, then one job per candidate, which runs
    the candidate's pairs in order.

    The jobs go in in the order the sweep reads them: the stored value's
    first, then each parameter's candidates, the parameter with the fewest
    first. A candidate that comes up once the clock is spent is left out,
    unless it is in the first chunk of a parameter the sweep has entered, so
    a parameter in flight still gives a reading, as `_run_candidates` does.
    A candidate stops at its first pair that differs from the stored
    value's, as `_profile` does, unless it keeps every pair for the
    per-case sets.
    """

    def __init__(self, source: str, examples: list, clock: _Clock):
        self.examples = examples
        self.clock = clock
        self.res = res_out(source)
        self.chunk = _pool_workers() or 8
        self.entered: set[str] = set()
        self.candidates: dict[str, list[Future]] = {}
        self.pool = ThreadPoolExecutor(max_workers=_pool_workers())
        self.stored = [self.pool.submit(_pair_profile, source, ex, self.res)
                       for ex in examples]

    def __enter__(self) -> "_TrainRuns":
        return self

    def __exit__(self, *exc) -> None:
        self.pool.shutdown(wait=True, cancel_futures=True)

    def submit(self, param: str, mods: list[str], keep_all: bool) -> None:
        """Queue a job for each of the parameter's candidate sources. The
        first parameter queued is the first the sweep enters, whatever the
        clock reads."""
        if not self.candidates:
            self.entered.add(param)
        self.candidates[param] = [
            self.pool.submit(self._run, param, index, mod, keep_all)
            for index, mod in enumerate(mods)]

    def _run(self, param: str, index: int, mod: str,
             keep_all: bool) -> list[PairRun] | None:
        """The candidate's pair runs in pair order, or None when the limit
        leaves it out. The stored value's jobs went in first, so they have
        started by the time this one waits on them."""
        if self.clock.spent() and not (param in self.entered
                                       and index < self.chunk):
            return None
        runs: list[PairRun] = []
        for ex, stored in zip(self.examples, self.stored, strict=True):
            runs.append(_pair_profile(mod, ex, self.res))
            if not keep_all and runs[-1][0] != stored.result()[0]:
                break
        return runs

    def stored_runs(self) -> Iterable[PairRun]:
        return (f.result() for f in self.stored)

    def rows(self, param: str, candidates: list, reference: list,
             want: bool) -> tuple[list, int]:
        """The rows of the candidates run, in candidate order, and how many
        there are, as `_run_candidates` gives them for the sweep's `test`:
        (value, fits, admitted cases). The rows stop at the first candidate
        the limit left out."""
        self.entered.add(param)
        rows: list = []
        for vals, job in zip(candidates, self.candidates[param], strict=True):
            runs = job.result()
            if runs is None:
                break
            if want:
                profile, passing = cases_of(runs, self.res)
                admits = frozenset.intersection(*passing) if passing else None
                rows.append((vals, profile == reference, admits))
            else:
                rows.append((vals, profile_of(runs, reference) == reference,
                             None))
        return rows, len(rows)


def stored_rows(
    facts: list[list[str]], types: list[str], defines: dict[str, int]
) -> list[tuple]:
    """The parameter's stored facts as value tuples: a Position column as
    its component tuple, an enum column as its define's value."""
    rows = []
    for args in facts:
        vals = []
        for a, t in zip(args, types):
            if t in POSITION_TYPES:
                vals.append(tuple(int(x) for x in _split_args(a[1:-1])))
            elif a.lstrip("-").isdigit():
                vals.append(int(a))
            else:
                vals.append(defines[a])
        rows.append(tuple(vals))
    return rows


def param_domains(
    types: list[str], stored: list[tuple], task, defines: dict[str, int]
) -> list[list]:
    """Each column's candidate domain, in column order. A Position column's
    domain follows the frame its stored values imply."""
    domains = []
    for i, t in enumerate(types):
        if t in ENUM_TYPES:
            domains.append(_enum_domain(t, defines))
        elif t == "Color":
            domains.append(_color_domain(task))
        elif t == "number":
            domains.append(_number_domain(task))
        else:
            domains.append(
                _position_domain(t, [s[i] for s in stored], _number_domain(task))
            )
    return domains


def _reading_cases(source: str, param: str) -> frozenset[str]:
    """The names the section marker above the parameter's decl in Params
    holds, each with the fields it fixes: `Derive(g=Iso)`. A parameter
    above every marker is shared, and the set is empty for it."""
    start, end = _comp_span(source, "Params")
    section = None
    for line in source.splitlines()[start:end]:
        if m := SECTION_RE.match(line.lstrip()):
            section = m.group(1)
        elif re.match(rf"\s*\.decl\s+{param}\s*\(", line):
            break
    if section is None:
        return frozenset()
    return frozenset(c.lstrip("$") for c in marker_names(section))


def _ctor_names(value: str) -> set[str]:
    """The constructor names a printed case value holds: `[$A($B), $C]`
    gives `A`, `B` and `C`."""
    return set(re.findall(r"\$(\w+)", value))


def _field_names(source: str) -> dict[str, list[str]]:
    """Each constructor's field names, in declaration order."""
    try:
        items = parse(source).items
    except ParseError:
        return {}
    return {m.group(1): re.findall(r"(\w+)\s*:", m.group(2))
            for it in items if isinstance(it, TypeDecl) and it.branches
            for m in BRANCH_RE.finditer(it.rhs)}


def _marker_test(source: str, res: bool, names: frozenset[str]):
    """A test of whether a printed case is one of the cases the marker
    names in `names` mark. A name marks the cases that take its
    constructor, with each field it fixes taking the constructor it fixes
    there. Where the `Choice` spells no case in full, a name marks the
    cases that take its constructor."""
    bare = {n.split("(", 1)[0].strip() for n in names}
    space = case_space(source)
    if not isinstance(space, Space):
        return lambda case: bool(_ctor_names(case) & bare)
    fields = _field_names(source)
    wanted = []
    for name in names:
        m = TERM_RE.match(name)
        if m is None:
            continue
        fixed = {}
        for part in (m.group(2) or "").split(","):
            key, eq, value = part.partition("=")
            if eq:
                fixed[key.strip()] = value.strip().lstrip("$")
        wanted.append((m.group(1), fixed))

    def marks(forced, ctor: str, fixed: dict[str, str]) -> bool:
        own = fields.get(ctor, [])
        return any(
            c == ctor and all(
                f in own and forced.get(node + (own.index(f),)) == v
                for f, v in fixed.items())
            for node, c in forced.items())

    def test(case: str) -> bool:
        forced = space.nodes(model_label(case, res))
        if forced is None:
            return bool(_ctor_names(case) & bare)
        return any(marks(forced, ctor, fixed) for ctor, fixed in wanted)

    return test


def _reading_runs(mod: str, examples: list, res: bool,
                  marked) -> list[frozenset[str]]:
    """Per pair, the cases that give a grid under `mod` and that `marked`
    holds to read the parameter. A case with conflicting or missing cells
    gives no grid. A `TiebreakResolution` solver's resolution column is
    left off each case. A run that fails raises its error."""
    out = []
    for ex in examples:
        actuals = parse_output(
            _run_source(build_source(mod), grid_to_facts(ex.input)))
        cases = {c.case for c in actuals
                 if not (c.error or c.conflicts or c.missing)}
        out.append(frozenset(
            c.rsplit("\t", 1)[0] if res else c
            for c in cases if marked(c)))
    return out


def _run_failed(err: RuntimeError) -> str:
    """The reason a sweep line gives for a run that failed: the first
    error line Souffle printed, or the error's first line."""
    lines = [ln.strip() for ln in str(err).splitlines() if ln.strip()]
    first = next((ln for ln in lines if ln.startswith("Error")),
                 lines[0] if lines else "")
    return mctx("the run failed: {error}").format(error=first)


def _undefined(source: str, param: str, extras: list, source_of,
               examples: list) -> tuple[frozenset[str], dict[object, bool]]:
    """The extras at which no case that reads the parameter is defined on
    every train pair, each mapped to whether those cases emit nothing on
    every pair; and the names of the cases that read the parameter.

    A value reproduces the pairs while its case fits the task, so a value
    that the pairs reproduce only because the reading cases emit nothing is
    no admitted value. A shared parameter is read by every case, and the
    stored profile already holds them, so only a parameter under a case
    marker is checked. Nor is one whose reading cases are undefined on some
    pair under the stored value too. `source_of` gives the source under one
    extra. A run that fails raises its error.
    """
    names = _reading_cases(source, param)
    if not names or not extras:
        return names, {}
    res = res_out(source)
    marked = _marker_test(source, res, names)
    if not frozenset.intersection(*_reading_runs(source, examples, res,
                                                 marked)):
        return names, {}

    def check(value):
        return _reading_runs(source_of(value), examples, res, marked)

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        runs = dict(zip(extras, executor.map(check, extras)))
    return names, {
        value: not any(per_pair)
        for value, per_pair in runs.items()
        if not frozenset.intersection(*per_pair)
    }


type SweepResult = tuple[str, str, str | tuple]
"""A parameter's line of the sweep, as `sweep_report` gives it: the
parameter, the status, and the detail, which is the reason text for a
`skip` status and a tuple for every other status."""


def sweep_report(
    stem: str,
    max_candidates: int = MAX_CANDIDATES,
    time_limit: float = TIME_LIMIT_SECONDS,
) -> list[SweepResult]:
    """Conditional sweep of each enumerable parameter.

    Sweeps one parameter at a time with the others at their stored values; an
    alternative value fits when it reproduces the stored value's variant
    profile on every train pair. A parameter's value may be a set (a symmetric
    member stores every fitting value), so the check is fitting == stored
    facts.

    Fitting values beyond the stored facts are re-run against the test
    pairs: a producer holding only the train pairs could pick any of them,
    so an extra that fails test is a would-be wrong prediction, and one
    that passes is gauge for this task instance.

    A parameter whose stored facts fail their singleton runs fits only as a
    set; it is re-swept whole (see _set_sweep), with candidate sets in
    place of candidate values.

    Above the cap the cross product of the domains gives way to the
    coordinate sweep (see _coordinate_candidates), which the cap bounds in
    turn. A slice smaller than that product is a partial sweep, and the
    status says so.

    `time_limit` is the wall-clock limit in seconds for the solver runs.
    The parameters run in order of candidate count, the cheapest first, and
    the clock is read between runs. Once the limit is spent, the parameter
    in flight reports as cut and the parameters behind it report as not
    swept for the reason "time limit". The report keeps the declaration
    order.

    A shared parameter is one every case reads, so the cases must admit
    a common value; the stored value is one, since every case passes under
    it. Each such parameter reports its per-case value sets too, from the
    same runs (see _case_result).

    A value fits only while a case that reads the parameter is defined on
    every train pair under it (see _undefined). The values the pairs
    reproduce only because those cases emit nothing leave the fitting
    values, and the detail names them.

    Returns (param, status, detail): status 'swept' carries
    (fitting, stored, types, verdicts, scope, gaps) — verdicts maps each
    extra fitting value to its test-pass bool, scope is None, and gaps is
    None or (the names of the reading cases, each undefined value mapped
    to whether those cases emit nothing on every pair) — 'swept-near' and
    'swept-cut' carry that shape with the scope (swept, whole),
    'swept-set' carries the same shape with frozensets of value tuples
    for fitting and verdict keys, 'swept-set-near' and 'swept-set-cut'
    add the scope to that, 'cases' carries (per_case, types, domain), and
    'skip' carries the reason.
    """
    # Macros expand first, so a GRID-fed parameter reads as ordinary facts and
    # a RIGID chart as an ordinary generated-name parameter; re-expansion at
    # build time is a no-op. Chart parameters report under their public names, and
    # their derived placed forms are elided rather than reported.
    path, task_id = solver_file(stem)
    source = expand_macros(path.read_text())
    task = load_task(task_id)
    defines = _lib_defines()
    s, e = _comp_span(source, "Params")
    params_text = "\n".join(source.splitlines()[s:e])

    shared = shared_params(source)
    params = comp_decls(source, "Params")
    placed = {public_param(n) for n in params if n.startswith(RIGID_CHART_PREFIX)}

    # The report keeps the declaration order, so each entry carries the
    # rank of its parameter and its place within that parameter.
    results: list[tuple[int, int, SweepResult]] = []
    prepared: list[tuple[int, str, list[str], list[tuple], list[tuple],
                        str, tuple | None]] = []
    for rank, (param, types) in enumerate(params.items()):
        if param in placed:
            continue
        if re.search(rf"\b{param}\s*\([^)]*\)\s*:-", params_text):
            results.append((rank, 0, (public_param(param), "skip", "derived")))
            continue
        facts = _param_facts(source, param)
        if not facts:
            results.append((rank, 0, (public_param(param), "skip", "0 facts")))
            continue
        if not all(t in ENUM_TYPES or t in ("Color", "number")
                   or t in POSITION_TYPES for t in types):
            results.append((rank, 0, (
                public_param(param), "skip",
                f"non-enumerable ({', '.join(types)})")))
            continue

        stored = stored_rows(facts, types, defines)
        domains = param_domains(types, stored, task, defines)

        # Stored values join the candidate set, so a stored value outside
        # the domain (a count above the dims, say) still reads as stored
        # rather than as a holistic table.
        candidates = sorted(set(itertools.product(*domains)) | set(stored))
        status, scope = "swept", None
        if len(candidates) > max_candidates:
            whole = len(candidates)
            candidates = _coordinate_candidates(stored, domains, max_candidates)
            # A slice that holds every candidate — the stored rows alone
            # over the cap — is a complete sweep and reports as one.
            if len(candidates) < whole:
                status, scope = "swept-near", (len(candidates), whole)
        prepared.append((rank, param, types, stored, candidates, status, scope))

    clock = _Clock(time_limit)
    reference: list[frozenset[str]] | None = None
    test_reference: list[frozenset[str]] | None = None
    base_cases: frozenset[str] = frozenset()
    ran = False
    # A spent limit costs the report the parameters that ask for the most
    # runs.
    order = sorted(prepared, key=lambda p: (len(p[4]), p[0]))
    with _TrainRuns(source, task.train, clock) as train_runs:
        # Every candidate's train runs go in up front, so no parameter
        # waits on another's slowest run. A parameter that may ask for the
        # per-case sets keeps every pair.
        for _rank, param, _types, _stored, candidates, _status, _scope in order:
            train_runs.submit(
                param, [swap_fact(source, param, v) for v in candidates],
                keep_all=(param in shared
                          and len(_param_facts(source, param)) == 1))
        for rank, param, types, stored, candidates, status, scope in order:
            if ran and clock.spent():
                results.append(
                    (rank, 0, (public_param(param), "skip", "time limit")))
                continue

            if reference is None:
                if shared:
                    reference, passing = cases_of(train_runs.stored_runs(),
                                                  train_runs.res)
                    base_cases = (frozenset.intersection(*passing) if passing
                                  else frozenset())
                else:
                    reference = profile_of(train_runs.stored_runs())
                ran = True
                if reference is None:
                    results.append((rank, 0, (
                        public_param(param), "skip", "stored value fails train")))
                    continue

            facts = _param_facts(source, param)
            # The per-case sets need every pair, so the profile's early return
            # goes only for the shared parameters this report covers.
            cases_wanted = (param in shared and len(base_cases) > 1
                            and len(facts) == 1)

            print(PROGRESS.format(
                name=public_param(param), count=len(candidates)),
                  file=sys.stderr)
            rows, run = train_runs.rows(param, candidates, reference,
                                        cases_wanted)
            ran = True
            fitting = [v for v, ok, _ in rows if ok]
            gaps = None
            if run < len(candidates) or set(stored) <= set(fitting):
                try:
                    names, undefined = _undefined(
                        source, param, sorted(set(fitting) - set(stored)),
                        lambda v, param=param: swap_fact(source, param, v),
                        task.train)
                except RuntimeError as err:
                    results.append((rank, 0, (
                        public_param(param), "skip", _run_failed(err))))
                    continue
                fitting = [v for v in fitting if v not in undefined]
                gaps = (names, undefined) if undefined else None

            if run < len(candidates):
                # A cut sweep reads part of the candidate set, so it reports
                # what it saw and leaves the test runs out.
                results.append((rank, 0, (
                    public_param(param), "swept-cut",
                    (fitting, stored, types, {}, (run, len(candidates)),
                     gaps))))
                continue

            case_result = _case_result(param, types, candidates, base_cases, rows) \
                if cases_wanted else None

            if not set(stored) <= set(fitting):
                results.append((rank, 0, _set_sweep(
                    source, param, stored, types, candidates, task, reference,
                    max_candidates, clock)))
                if case_result:
                    results.append((rank, 1, case_result))
                continue

            verdicts: dict[tuple, bool] = {}
            extras = sorted(set(fitting) - set(stored))
            if extras and set(stored) <= set(fitting):
                if test_reference is None:
                    test_reference = _profile(source, task.test)
                if test_reference is None:
                    verdicts = {e: False for e in extras}
                else:
                    def test_check(vals, param=param, ref=test_reference):
                        return _profile(swap_fact(source, param, vals),
                                        task.test, ref) == ref

                    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                        verdicts = dict(zip(extras, executor.map(test_check, extras)))
            detail = (fitting, stored, types, verdicts, scope, gaps)
            results.append((rank, 0, (public_param(param), status, detail)))
            if case_result:
                results.append((rank, 1, case_result))
    return [r for _, _, r in sorted(results, key=lambda r: r[:2])]


def _case_result(
    param: str,
    types: list[str],
    candidates: list[tuple],
    base_cases: frozenset[str],
    rows: list[tuple[tuple, bool, frozenset[str] | None]],
) -> SweepResult | None:
    """The per-case entry for one shared parameter, or None when the cases
    admit one value set.

    A case admits a value when it reproduces every train pair under it. A
    case that admits the whole domain never reads the parameter, so the
    parameter goes under the marker of the cases that read it; a case that
    admits more than the narrowest case is one the pairs do not exercise
    the parameter under.
    """
    per_case = {
        case: frozenset(v for v, _, admits in rows if admits and case in admits)
        for case in base_cases
    }
    if len(set(per_case.values())) < 2:
        return None
    return (public_param(param), "cases", (per_case, types, frozenset(candidates)))


def _coordinate_candidates(
    stored: list[tuple], domains: list[list], limit: int
) -> list[tuple]:
    """The candidate rows one column-change from the stored facts.

    The stored rows head the list, and each of their columns runs through
    that column's domain with the other columns held. The whole sweep is
    the cross product of the domains; this is its coordinate slice. The
    rows come one per (stored row, column) in turn, so `limit` cuts every
    column alike. The cut never reaches a stored row, so stored rows above
    the limit are the whole list.
    """
    rows = list(dict.fromkeys(stored))
    seen = set(rows)
    slices = [
        [row[:i] + (value,) + row[i + 1:] for value in domain]
        for row in rows
        for i, domain in enumerate(domains)
    ]
    for step in itertools.zip_longest(*slices):
        for row in step:
            if row is None or row in seen:
                continue
            if len(rows) >= limit:
                return rows
            rows.append(row)
            seen.add(row)
    return rows


def _neighborhood(
    stored: list[tuple], singles: list[tuple], limit: int
) -> list[frozenset]:
    """The candidate sets one row-change from the stored facts, `limit` of
    them at most.

    A change is a stored row reassigned to another candidate value, a stored
    row dropped, or a non-stored candidate added; the other rows keep their
    stored values. The stored facts head the list, so the fitting sets read
    as in the whole sweep. The sets come one change per stored row in turn,
    so the limit cuts every row alike.
    """
    stored_set = frozenset(stored)
    sets = [stored_set]
    seen = {stored_set}
    changes = []
    for row in dict.fromkeys(stored):
        rest = stored_set - {row}
        changes.append([rest] + [rest | {value} for value in singles])
    changes.append([stored_set | {value} for value in singles])
    for step in itertools.zip_longest(*changes):
        for value in step:
            if not value or value in seen:
                continue
            if len(sets) >= limit:
                return sets
            sets.append(value)
            seen.add(value)
    return sets


def _set_sweep(
    source: str,
    param: str,
    stored: list[tuple],
    types: list[str],
    singles: list[tuple],
    task,
    reference: list[frozenset[str]],
    max_candidates: int,
    clock: _Clock,
) -> SweepResult:
    """Sweep a parameter whose facts fit only together, as one unit.

    Candidate values are the non-empty subsets of the singleton candidates;
    each replaces the whole parameter. Above the cap the subsets give way to
    the one-change neighborhood of the stored facts (see _neighborhood),
    which the cap bounds in turn, and the status names the part it swept.
    Fitting and test-refutation read as in the singleton sweep, over sets. A
    sweep the limit cuts reports the sets it ran of the sets it holds.

    Zero is absence, so a 0 in a number column stands as a candidate only
    where the stored facts already carry one in that column.
    """
    name = public_param(param)
    blank = {i for i, t in enumerate(types)
             if t == "number" and all(s[i] != 0 for s in stored)}
    singles = [v for v in singles if all(v[i] != 0 for i in blank)]
    n_sets = 2 ** len(singles) - 1
    status, scope = "swept-set", None
    if n_sets > max_candidates:
        subsets = _neighborhood(stored, singles, max_candidates)
        if len(subsets) < n_sets:
            status, scope = "swept-set-near", (len(subsets), n_sets)
    else:
        subsets = [
            frozenset(c)
            for r in range(1, len(singles) + 1)
            for c in itertools.combinations(singles, r)
        ]
    stored_set = frozenset(stored)

    def test(value):
        profile = _profile(swap_facts(source, param, sorted(value)),
                           task.train, reference)
        return value if profile == reference else None

    print(PROGRESS.format(name=name, count=len(subsets)),
          file=sys.stderr)
    rows, run = _run_candidates(test, subsets, clock)
    fitting = [f for f in rows if f]
    gaps = None
    if run < len(subsets) or stored_set in fitting:
        try:
            names, undefined = _undefined(
                source, param, sorted(set(fitting) - {stored_set}, key=sorted),
                lambda value: swap_facts(source, param, sorted(value)),
                task.train)
        except RuntimeError as err:
            return (name, "skip", _run_failed(err))
        fitting = [f for f in fitting if f not in undefined]
        gaps = (names, undefined) if undefined else None
    if run < len(subsets):
        return (name, "swept-set-cut",
                (fitting, stored, types, {}, (run, len(subsets)), gaps))

    verdicts: dict[frozenset, bool] = {}
    extras = sorted(set(fitting) - {stored_set}, key=sorted)
    if extras and stored_set in fitting:
        test_reference = _profile(source, task.test)
        if test_reference is None:
            verdicts = {e: False for e in extras}
        else:
            def test_check(value):
                profile = _profile(
                    swap_facts(source, param, sorted(value)), task.test,
                    test_reference)
                return profile == test_reference

            with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
                verdicts = dict(zip(extras, executor.map(test_check, extras)))
    return (name, status, (fitting, stored, types, verdicts, scope, gaps))


def _mag_vec(vals: tuple, types: list[str]) -> list[int]:
    """Magnitude components of a value tuple: number args as-is, the
    absolute components of Offset/Box args."""
    out: list[int] = []
    for v, t in zip(vals, types):
        if t == "number":
            out.append(v)
        elif t in MAG_POSITION_TYPES:
            out.extend(abs(x) for x in v)
    return out


def _num_peer(e: tuple, s: tuple, types: list[str]) -> bool:
    """e differs from s only in magnitude args — number, Offset, Box — a
    peer magnitude, not a peer identity. Nominal args (enums, Color,
    Ident, cell Positions) must match."""
    mag = {"number"} | MAG_POSITION_TYPES
    return all(e[i] == s[i] for i, t in enumerate(types) if t not in mag)


def _num_below(e: tuple, s: tuple, types: list[str]) -> bool:
    """e is a smaller magnitude reading of s: nominal args equal, magnitude
    components no larger, at least one strictly smaller."""
    em, sm = _mag_vec(e, types), _mag_vec(s, types)
    return (_num_peer(e, s, types)
            and all(a <= b for a, b in zip(em, sm))
            and any(a < b for a, b in zip(em, sm)))


def _refuted_note(param: str, determined: AbstractSet[str]) -> str:
    """What a refuted extra means for this parameter: a determination that
    reproduces the stored value already picks it from train; without one,
    such a determination is open."""
    return (mctx("the determination picks the stored value")
            if param in determined
            else mctx("a determination from train alone could pick it"))


def _gap_clauses(gaps, shown) -> list[str]:
    """The clauses on the values the pairs reproduce only because no case
    that reads the parameter is defined on every train pair. `shown`
    renders a list of values."""
    if not gaps:
        return []
    names, undefined = gaps
    label = ", ".join(f"`{n}`" for n in sorted(names))
    nothing = [v for v, empty in undefined.items() if empty]
    partial = [v for v, empty in undefined.items() if not empty]
    parts = []
    if nothing:
        parts.append(mctx(
            "the {label} cases are undefined on every train pair at {shown}").format(
            label=label, shown=shown(sorted(nothing))))
    if partial:
        parts.append(mctx(
            "no {label} case is defined on every train pair at {shown}").format(
            label=label, shown=shown(sorted(partial))))
    return parts


def _gaps(detail: tuple) -> tuple | None:
    """The gaps a swept line's detail carries; None where it carries
    none."""
    return detail[5] if len(detail) > 5 else None


def render_sweep(
    results: list[SweepResult],
    determined: AbstractSet[str] = frozenset(),
) -> list[str]:
    """One line per result; ` ✓` marks a parameter the sweep settles.

    `determined` holds the parameters whose determination reproduces the
    stored value, so an extra the test refutes is already picked from train
    for them, and the line says so.

    The mark goes on every line whose fitting values are the stored
    ones, in each of its forms — `unique`, `set of N`, `unique as a
    set` — so a reader keys on the mark rather than on one form. A
    partial sweep covers part of the candidate set, so its line names
    that scope and drops the mark, in the value forms and the set form
    alike. A value the pairs reproduce only because the cases that read
    the parameter emit nothing is no fitting value, and its own clause
    names it.
    """
    defines = _lib_defines()
    names = {v: k for k, v in defines.items()}

    def show(vals: tuple, types: list[str]) -> str:
        return "(" + ", ".join(
            names.get(v, str(v)) if t in ENUM_TYPES else _render_arg(v)
            for v, t in zip(vals, types)
        ) + ")"

    lines = []
    for param, status, detail in results:
        if isinstance(detail, str):
            lines.append(mctx("{param}: not swept — {detail}").format(
                param=param, detail=detail))
            continue
        if status == "cases":
            lines.append(_render_cases(param, detail, show))
            continue
        if status in ("swept-set", "swept-set-near", "swept-set-cut"):
            fitting, stored, types, verdicts = detail[:4]
            gaps = _gaps(detail)
            stored_set = frozenset(stored)
            scope = mctx("swept whole")
            if status == "swept-set-near":
                swept, whole = detail[4]
                scope = mctx("swept single-row changes; {swept} of {whole} "
                             "sets").format(swept=swept, whole=whole)
            elif status == "swept-set-cut":
                run, whole = detail[4]
                scope = mctx("cut by the time limit; {run} of {whole} "
                             "sets").format(run=run, whole=whole)

            def show_value(value, types=types):
                return "{" + ", ".join(show(v, types) for v in sorted(value)) + "}"

            def show_values(values):
                return "[" + ", ".join(show_value(v) for v in values) + "]"

            shown_s = show_value(stored_set)
            gap_parts = _gap_clauses(
                gaps, lambda vs: show_values(sorted(vs, key=sorted)))
            if set(fitting) == {stored_set}:
                mark = " ✓" if status == "swept-set" else ""
                lines.append("; ".join([mctx(
                    "{param}: unique as a set = {shown}{mark} (facts fit only "
                    "together; {scope})").format(
                    param=param, shown=shown_s, mark=mark, scope=scope)]
                    + gap_parts))
                continue
            extras = sorted(set(fitting) - {stored_set}, key=sorted)
            refuted = [e for e in extras if not verdicts.get(e, False)]
            passing = [e for e in extras if verdicts.get(e, False)]
            parts = [
                mctx("stored {shown} ({scope})").format(
                    shown=shown_s, scope=scope),
                mctx("train also admits sets {shown}").format(
                    shown=show_values(extras)),
            ]
            if refuted:
                parts.append(REFUTES.format(
                    shown=show_values(refuted),
                    note=_refuted_note(param, determined)))
            if passing:
                parts.append(PASSING.format(shown=show_values(passing)))
            lines.append(f"{param}: " + "; ".join(parts + gap_parts))
            continue
        fitting, stored, types, verdicts = detail[:4]
        gaps = _gaps(detail)
        scope = ""
        if status == "swept-near":
            swept, whole = detail[4]
            scope = " " + mctx(
                "(swept single-column changes; {swept} of {whole} "
                "values)").format(swept=swept, whole=whole)
        elif status == "swept-cut":
            run, whole = detail[4]
            scope = " " + mctx(
                "(cut by the time limit; {run} of {whole} values)").format(
                    run=run, whole=whole)
        vset, sset = set(fitting), set(stored)
        def shown(vals, types=types):
            return ", ".join(show(v, types) for v in vals)

        shown_s = shown(stored)
        gap_parts = _gap_clauses(gaps, lambda vs: f"[{shown(vs)}]")
        if vset == sset:
            mark = "" if scope else " ✓"
            if len(sset) == 1:
                head = mctx("{param}: unique = {shown}{mark}{scope}").format(
                    param=param, shown=shown_s, mark=mark, scope=scope)
            else:
                head = mctx(
                    "{param}: set of {count} = [{shown}]{mark}{scope}").format(
                    param=param, count=len(sset), shown=shown_s, mark=mark,
                    scope=scope)
            lines.append("; ".join([head] + gap_parts))
            continue
        # Each finding about the extras gets its own clause, so a refuted
        # extra cannot hide a surviving one.
        extras = sorted(vset - sset)
        refuted = [e for e in extras if not verdicts.get(e, False)]
        passing = [e for e in extras if verdicts.get(e, False)]
        parts = [mctx("stored {shown}").format(shown=shown_s),
                 mctx("train also admits [{shown}]").format(
                     shown=shown(extras))]
        if refuted:
            parts.append(REFUTES.format(
                shown=f"[{shown(refuted)}]",
                note=_refuted_note(param, determined)))
        if passing:
            parts.append(PASSING.format(shown=f"[{shown(passing)}]"))
            kind = [e for e in passing
                    if not any(_num_peer(e, s, types) for s in sset)]
            if kind:
                parts.append(
                    mctx("[{shown}] and stored are open values, differing "
                         "in a nominal argument").format(shown=shown(kind)))
            below = sorted(
                e for e in passing if any(_num_below(e, s, types) for s in sset)
            )
            if below:
                parts.append(
                    mctx("[{shown}] fit and are smaller than stored").format(
                        shown=shown(below)))
        lines.append(f"{param}: " + "; ".join(parts + gap_parts) + scope)
    return lines


def _render_cases(param: str, detail: tuple, show) -> str:
    """One line for a shared parameter whose cases admit different values."""
    per_case, types, domain = detail
    groups: dict[frozenset, list[str]] = {}
    for case, values in sorted(per_case.items()):
        groups.setdefault(values, []).append(case)
    order = sorted(groups.items(), key=lambda g: (len(g[0]), sorted(g[1])))
    least = order[0][0]
    parts = [mctx("{param}: the cases admit different values").format(
        param=param)]
    for values, cases in order:
        label = ", ".join(cases)
        s = "" if len(cases) > 1 else "s"
        shown = ", ".join(show(v, types) for v in sorted(values))
        if values == domain:
            parts.append(mctx(
                "{label} admit{s} the whole domain [{shown}], so {label} never "
                "read{s} {param} — move {param} under the marker of the cases "
                "that read it").format(
                label=label, s=s, shown=shown, param=param))
        elif values != least:
            parts.append(mctx(
                "{label} admit{s} [{shown}], so the pairs do not exercise "
                "{param} under {label}").format(
                label=label, s=s, shown=shown, param=param))
        else:
            parts.append(mctx("{label} admit{s} [{shown}]").format(
                label=label, s=s, shown=shown))
    return "; ".join(parts)
