"""Run a solver in solve mode and compare its output to the stored pairs."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache

from arc.task import load as load_task
from dl.dlparse import Decl, ParseError, parse
from dl.facts import Candidate, grid_to_facts, parse_output
from dl.paths import SOLVERS_DIR
from dl.souffle import _pool_workers, _run_source, compile_check
from dl.source import build_source


def run_dl(
    task_id: str, input_rows: list[list[int]], stem: str | None = None
) -> list[Candidate]:
    dl_path = SOLVERS_DIR / f"{stem or task_id}.dl"
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")

    return parse_output(
        _run_source(build_source(dl_path.read_text()), grid_to_facts(input_rows),
                    solver_path=dl_path)
    )


def compile_error(stem: str) -> str | None:
    """Souffle's complaint about `stem`'s solve-mode program, or None when it
    compiles. A source-level error fails every pair the same way, so the
    callers check it once instead of reporting one copy per pair."""
    return compile_check(build_source((SOLVERS_DIR / f"{stem}.dl").read_text()))


def res_out(source: str) -> bool:
    """True when `out`'s trailing column is typed `TiebreakResolution` —
    resolution semantics: the emitted grid set must equal the accepted set."""
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
    return res_out((SOLVERS_DIR / f"{stem}.dl").read_text())


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


def _every_slot_landed(slots: list[int | None], n: int) -> bool:
    """A rule alt is a peer model: each accepted grid is one case's output,
    so some variant must land on every slot."""
    return set(slots) == set(range(n))


def _profile(mod_source: str, examples: list) -> list[frozenset[str]] | None:
    """Per-pair variant-name sets under this source; None on any failure.

    A modified source must reproduce the original's profile, not merely
    pass: a wrong value or a deleted rule can silence a Choice case, and a
    vanished variant is never checked. A `TiebreakResolution` solver's
    variant names are enumeration terms with no stable identity, so its
    profile is the grid set instead.
    """
    res = res_out(mod_source)
    profile = []
    for ex in examples:
        try:
            actuals = parse_output(
                _run_source(build_source(mod_source), grid_to_facts(ex.input))
            )
        except Exception:
            return None
        accepted = _accepted(ex)
        names = set()
        grids = set()
        slots: list[int | None] = []
        for c in actuals:
            slot = _slot_of(c.grid, accepted)
            if c.error or slot is None or c.conflicts or c.missing:
                return None
            names.add(c.variant)
            grids.add(_grid_key(c.grid))
            slots.append(slot)
        if res:
            if grids != {_grid_key(g) for g in accepted}:
                return None
            profile.append(frozenset(grids))
        else:
            if ex.alt is not None and ex.alt.kind == "rule":
                if not _every_slot_landed(slots, len(accepted)):
                    return None
            profile.append(frozenset(names))
    return profile


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
        slots = [_slot_of(c.grid, accepted) for c in actuals]
        variants = [
            VariantResult(
                name=c.variant,
                ok=(not c.error) and slot is not None
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
        distinct = {_grid_key(v.actual) for v in variants}
        if rule_alt:
            ok = ok and _every_slot_landed(slots, len(accepted))
        if res_out_stem(stem):
            # Resolution semantics: a tiebreak is two-way, and every
            # accepted grid must also be emitted.
            if len(distinct) > 2:
                return PairResult(
                    kind=kind,
                    idx=idx,
                    ok=False,
                    error=f"tiebreak is two-way: {len(distinct)} distinct "
                          "grids emitted",
                    expected=ex.output,
                    accepted=accepted,
                    variants=variants,
                )
            ok = ok and distinct == {_grid_key(g) for g in accepted}
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
    task_id = stem.split("_", 1)[0]
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
