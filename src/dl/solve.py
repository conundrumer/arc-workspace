"""Run a solver in solve mode and compare its output to the stored pairs."""

import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from arc.task import load as load_task
from dl.dlparse import Decl, ParseError, parse
from dl.facts import Candidate, grid_to_facts, parse_output
from dl.paths import SOLVERS_DIR
from dl.souffle import _pool_workers, _run_source, compile_check
from dl.source import build_source

TASK_ID_RE = re.compile(r"[0-9a-f]{8}")


def task_id_of(arg: str) -> str:
    """The task a solver argument names: the leading eight hex characters of
    its file name, so a variant such as `abcd1234_alt.dl` carries the id of
    the task it belongs to. A `.dl` suffix is dropped first, and a file name
    that leads with no id is itself the id."""
    name = Path(arg).name.removesuffix(".dl")
    found = TASK_ID_RE.match(name)
    return found.group() if found else name


def solver_name(stem: str) -> str:
    """The solver file a stem argument names, as a finding line gives it: the
    argument as the caller wrote it, with `.dl` where it has none."""
    return stem if stem.endswith(".dl") else f"{stem}.dl"


def solver_file(arg: str) -> tuple[Path, str]:
    """The solver file a caller's argument names, with its task id. The
    argument is a stem (`8403a5d5`), a file name (`8403a5d5.dl`), or a path
    to a `.dl` file, relative to the working directory or absolute. A path
    that exists as given is that file; every other argument resolves under
    programs/solvers/, where a bare stem names a corpus solver."""
    path = Path(solver_name(arg))
    if not path.exists():
        path = SOLVERS_DIR / path
    return path, task_id_of(path.name)


def run_dl_source(
    source: str, input_rows: list[list[int]], solver_path: Path | None = None
) -> list[Candidate]:
    """Run one grid through a solver source. `solver_path` is the file that
    source came from, which a CPU-limit failure reports against."""
    return parse_output(
        _run_source(build_source(source), grid_to_facts(input_rows),
                    solver_path=solver_path)
    )


def run_dl(
    task_id: str, input_rows: list[list[int]], stem: str | None = None
) -> list[Candidate]:
    dl_path = solver_file(stem or task_id)[0]
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")

    return run_dl_source(dl_path.read_text(), input_rows, solver_path=dl_path)


def compile_error(stem: str) -> str | None:
    """Souffle's complaint about `stem`'s solve-mode program, or None when it
    compiles. A source-level error fails every pair the same way, so the
    callers check it once instead of reporting one copy per pair."""
    return compile_check(build_source(solver_file(stem)[0].read_text()))


def res_out(source: str) -> bool:
    """True when `out`'s trailing column is typed `TiebreakResolution` —
    resolution semantics: the emitted grid set is the pair's candidate."""
    try:
        program = parse(source)
    except ParseError:
        return False
    for it in program.items:
        if isinstance(it, Decl) and it.name == "out":
            return bool(it.fields) and it.fields[-1].type == "TiebreakResolution"
    return False


@lru_cache
def res_out_stem(stem: str) -> bool:
    return res_out(solver_file(stem)[0].read_text())


def _grid_key(grid: list[list[int]]) -> tuple:
    return tuple(tuple(row) for row in grid)


def _accepted(ex) -> list[list[list[int]]]:
    """The grids the pair accepts: the stored output first, then its alt."""
    accepted = [ex.output]
    if ex.alt is not None and ex.alt.kind in ("tiebreak", "rule"):
        accepted.append(ex.alt.grid)
    return accepted


def _slot_of(grid: list[list[int]], accepted: list[list[list[int]]]) -> int | None:
    """The accepted slot `grid` lands on: 0 for the main output, 1.. for the
    alts in their order. None when it lands on no slot."""
    key = _grid_key(grid)
    for slot, g in enumerate(accepted):
        if _grid_key(g) == key:
            return slot
    return None


def _sample(ex) -> list[list[list[int]]]:
    """The grids the task file gives for a pair as a sample of its candidate:
    the stored output, and a tiebreak alt when the pair has one."""
    sample = [ex.output]
    if ex.alt is not None and ex.alt.kind == "tiebreak":
        sample.append(ex.alt.grid)
    return sample


def _same_shape(a: list[list[int]], b: list[list[int]]) -> bool:
    return len(a) == len(b) and all(len(x) == len(y) for x, y in zip(a, b))


def _free_cells(sample: list[list[list[int]]]) -> set[tuple[int, int]] | None:
    """The cells where the pair's stored grids differ: the tiebreak the task
    leaves free. None when the stored grids have different shapes."""
    first = sample[0]
    cells = set()
    for grid in sample[1:]:
        if not _same_shape(grid, first):
            return None
        for r, (row, frow) in enumerate(zip(grid, first)):
            for c, (v, fv) in enumerate(zip(row, frow)):
                if v != fv:
                    cells.add((r, c))
    return cells


def _resolution_error(grids: list[list[list[int]]], ex) -> str | None:
    """Why the emitted grids are not the pair's candidate, or None when they
    are. A candidate is the set of a pair's accepted outputs that differ only
    in a tiebreak, and every resolution is an accepted output, so the grids
    the task file stores are a sample of the emitted set. The emitted set must
    hold every stored grid, and its grids must agree wherever the stored grids
    agree."""
    sample = _sample(ex)
    free = _free_cells(sample)
    if free is None:
        return "the pair's stored grids have different shapes"
    emitted = {_grid_key(g) for g in grids}
    for i, grid in enumerate(sample):
        if _grid_key(grid) not in emitted:
            name = "the stored output" if i == 0 else "the tiebreak alt"
            return f"{name} is not among the emitted grids"
    first = sample[0]
    for grid in grids:
        if not _same_shape(grid, first):
            return ("an emitted grid has a different shape from the stored "
                    "grids")
        for r, (row, frow) in enumerate(zip(grid, first)):
            for c, (v, fv) in enumerate(zip(row, frow)):
                if v != fv and (r, c) not in free:
                    return (f"emitted grids differ at cell ({r}, {c}), where "
                            "the stored grids agree")
    return None


def _every_slot_landed(slots: list[int | None], n: int) -> bool:
    """A rule alt is a peer model: each accepted grid is one case's output,
    so some variant must land on every slot."""
    return set(slots) == set(range(n))


def _pair_entry(actuals: list, ex, res: bool) -> frozenset | None:
    """One pair's profile entry, or None when the pair fails."""
    accepted = _accepted(ex)
    names = set()
    grids = set()
    slots: list[int | None] = []
    for c in actuals:
        slot = _slot_of(c.grid, accepted)
        if c.error or c.conflicts or c.missing:
            return None
        if slot is None and not res:
            return None
        names.add(c.case)
        grids.add(_grid_key(c.grid))
        slots.append(slot)
    if res:
        if not actuals or _resolution_error([c.grid for c in actuals], ex):
            return None
        return frozenset(grids)
    if ex.alt is not None and ex.alt.kind == "rule":
        if not _every_slot_landed(slots, len(accepted)):
            return None
    return frozenset(names)


def _passing(actuals: list, ex) -> frozenset[str]:
    """The variants that reproduce this pair: no error, no conflict, no
    missing cell, and a grid the pair accepts."""
    accepted = _accepted(ex)
    return frozenset(
        c.case for c in actuals
        if not c.error and not c.conflicts and not c.missing
        and _slot_of(c.grid, accepted) is not None
    )


def _pair_profile(mod_source: str, ex, res: bool
                  ) -> tuple[frozenset[str] | None, frozenset[str]]:
    """One pair's profile entry and its passing-variant set. The entry is
    None when the pair fails."""
    try:
        actuals = parse_output(
            _run_source(build_source(mod_source), grid_to_facts(ex.input))
        )
    except Exception:
        actuals = None
    if actuals is None:
        return None, frozenset()
    return _pair_entry(actuals, ex, res), _passing(actuals, ex)


type PairRun = tuple[frozenset[str] | None, frozenset[str]]
"""One pair's profile entry, None when the pair fails, and its
passing-variant set, as `_pair_profile` gives them."""


def _profile(
    mod_source: str, examples: list,
    reference: list[frozenset[str]] | None = None,
) -> list[frozenset[str]] | None:
    """Per-pair variant-name sets under this source; None on any failure.

    A modified source must reproduce the original's profile, not merely
    pass: a wrong value or a deleted rule can silence a Choice case, and a
    vanished variant is never checked. A `TiebreakResolution` solver's
    variant names are enumeration terms with no stable identity, so its
    profile is the grid set instead.

    A failing pair ends the run. With `reference`, so does the first pair
    whose entry differs from the reference's: the profile returned then
    holds the pairs run so far, and it differs from the reference.
    """
    res = res_out(mod_source)
    return profile_of((_pair_profile(mod_source, ex, res) for ex in examples),
                      reference)


def profile_of(runs: Iterable[PairRun],
               reference: list[frozenset[str]] | None = None
               ) -> list[frozenset[str]] | None:
    """The profile the pair runs give, read in pair order, as `_profile`
    reads it; a run is taken only when the ones before it leave the
    profile open."""
    profile: list[frozenset[str]] = []
    for i, (entry, _) in enumerate(runs):
        if entry is None:
            return None
        profile.append(entry)
        if reference is not None and (i >= len(reference)
                                      or entry != reference[i]):
            return profile
    return profile


def _profile_cases(
    mod_source: str, examples: list
) -> tuple[list[frozenset[str]] | None, list[frozenset[str]] | None]:
    """The profile of this source, and its per-pair passing-variant sets.

    A passing-variant set per pair needs every pair, so a failing pair does
    not end the run; the extra runs are the cost of asking for the sets. A
    `TiebreakResolution` solver has no such sets, and there a failing pair
    ends the run as it does in `_profile`.
    """
    res = res_out(mod_source)
    return cases_of((_pair_profile(mod_source, ex, res) for ex in examples),
                    res)


def cases_of(
    runs: Iterable[PairRun], res: bool
) -> tuple[list[frozenset[str]] | None, list[frozenset[str]] | None]:
    """The profile and the passing-variant sets the pair runs give, read in
    pair order, as `_profile_cases` reads them; `res` is whether the
    solver's `out` ends in a `TiebreakResolution`."""
    profile: list[frozenset[str]] | None = []
    passing: list[frozenset[str]] | None = None if res else []
    for entry, ok in runs:
        if passing is not None:
            passing.append(ok)
        if entry is None:
            profile = None
            if passing is None:
                return None, None
        elif profile is not None:
            profile.append(entry)
    return profile, passing


@dataclass
class VariantResult:
    name: str  # '' when out has no trailing column
    ok: bool
    actual: list[list[int]]
    conflicts: list[tuple[int, int]] = field(default_factory=list)
    missing: list[tuple[int, int]] = field(default_factory=list)
    error: str | None = None  # the variant's cells describe no grid
    slot: int | None = None  # the accepted slot landed on, under a rule alt


@dataclass
class PairResult:
    kind: str
    idx: int
    ok: bool
    error: str | None = None
    expected: list[list[int]] | None = None
    accepted: list[list[list[int]]] | None = None
    variants: list[VariantResult] = field(default_factory=list)
    rule_alt: bool = False  # the pair's alt is a peer model's output


@dataclass
class TaskResult:
    stem: str
    pairs: list[PairResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.pairs)

    @property
    def passes(self) -> int:
        return sum(1 for p in self.pairs if p.ok)

    @property
    def all_pass(self) -> bool:
        return all(p.ok for p in self.pairs) and not slot_flips(self.pairs)


def slot_flips(pairs: list[PairResult]) -> list[str]:
    """Cases landing on different accepted slots across two rule-alt pairs.
    A case is one model, so it gives that model's output in every pair, and
    a case that gives the main output in one pair and the alt in another
    follows no model."""
    seen: dict[str, tuple[str, int]] = {}
    findings = []
    for p in pairs:
        if not p.rule_alt:
            continue
        pair = f"{p.kind}[{p.idx}]"
        for v in p.variants:
            if v.slot is None:
                continue
            first = seen.setdefault(v.name, (pair, v.slot))
            if first[1] != v.slot:
                findings.append(
                    f"case {v.name or '(out)'} lands on slot {first[1]} in "
                    f"{first[0]} and slot {v.slot} in {pair}"
                )
    return findings


def case_coverage(pairs: list[PairResult]) -> list[str]:
    """Cases silent on some pair, and cases that flip accepted slots. A case
    is a complete model, so the emitted variant set must be the same across
    all pairs."""
    sets: dict[str, set[str]] = {}
    for p in pairs:
        if p.error or not p.variants:
            return []  # pair-level failure already reported
        sets[f"{p.kind}[{p.idx}]"] = {v.name for v in p.variants}
    union = set().union(*sets.values())
    return [
        f"case {name or '(out)'} silent on {pair}"
        for pair, s in sorted(sets.items())
        for name in sorted(union - s)
    ] + slot_flips(pairs)


def run_pair(stem: str, task_id: str, kind: str, idx: int, ex) -> PairResult:
    try:
        actuals = run_dl(task_id, ex.input, stem=stem)
        accepted = _accepted(ex)
        rule_alt = ex.alt is not None and ex.alt.kind == "rule"
        res = res_out_stem(stem)
        slots = [_slot_of(c.grid, accepted) for c in actuals]
        variants = [
            VariantResult(
                name=c.case,
                # A resolution solver emits the whole candidate, which may
                # hold grids the task file does not store, so a grid outside
                # the stored ones is judged by the pair-level check below.
                ok=(not c.error) and (res or slot is not None)
                   and not c.conflicts and not c.missing,
                actual=c.grid,
                conflicts=c.conflicts,
                missing=c.missing,
                error=c.error,
                slot=slot if rule_alt else None,
            )
            for c, slot in zip(actuals, slots, strict=True)
        ]
        ok = bool(variants) and all(v.ok for v in variants)
        if rule_alt:
            ok = ok and _every_slot_landed(slots, len(accepted))
        if res and ok:
            error = _resolution_error([v.actual for v in variants], ex)
            if error is not None:
                return PairResult(
                    kind=kind,
                    idx=idx,
                    ok=False,
                    error=error,
                    expected=ex.output,
                    accepted=accepted,
                    variants=variants,
                )
        return PairResult(
            kind=kind,
            idx=idx,
            ok=ok,
            expected=ex.output,
            accepted=accepted,
            variants=variants,
            rule_alt=rule_alt,
        )
    except Exception as e:
        return PairResult(
            kind=kind, idx=idx, ok=False, error=f"{type(e).__name__}: {e}"
        )


def _pair_work(stem: str) -> list[tuple]:
    """Build (stem, task_id, kind, idx, ex) tuples for every pair of `stem`."""
    task_id = solver_file(stem)[1]
    task = load_task(task_id)
    work = []
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            work.append((stem, task_id, kind, idx, ex))
    return work


def run_task(stem: str) -> TaskResult:
    """Single-task entry: pairs run in parallel."""
    work = _pair_work(stem)
    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        pairs = list(executor.map(lambda w: run_pair(*w), work))
    return TaskResult(stem=stem, pairs=pairs)
