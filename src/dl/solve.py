"""Run a solver in solve mode and compare its output to the stored pairs."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from arc.task import load as load_task
from dl.facts import grid_to_facts, parse_output
from dl.paths import SOLVERS_DIR
from dl.souffle import _pool_workers, _run_source
from dl.source import build_source


def run_dl(
    task_id: str, input_rows: list[list[int]], stem: str | None = None
) -> list[tuple[str, list[list[int]], list[tuple[int, int]], list[tuple[int, int]]]]:
    dl_path = SOLVERS_DIR / f"{stem or task_id}.dl"
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")

    return parse_output(
        _run_source(build_source(dl_path.read_text()), grid_to_facts(input_rows))
    )


def _profile(mod_source: str, examples: list) -> list[frozenset[str]] | None:
    """Per-pair variant-name sets under this source; None on any failure.

    A modified source must reproduce the original's profile, not merely
    pass: a wrong fill or a deleted rule can silence a Choice case, and a
    vanished variant is never checked.
    """
    profile = []
    for ex in examples:
        try:
            actuals = parse_output(
                _run_source(build_source(mod_source), grid_to_facts(ex.input))
            )
        except Exception:
            return None
        accepted = [ex.output]
        if ex.alt is not None and ex.alt.kind == "tiebreak":
            accepted.append(ex.alt.grid)
        names = set()
        for variant, grid, conflicts, missing in actuals:
            if grid not in accepted or conflicts or missing:
                return None
            names.add(variant)
        profile.append(frozenset(names))
    return profile


@dataclass
class VariantResult:
    name: str  # '' when out has no trailing column
    ok: bool
    actual: list[list[int]]
    conflicts: list[tuple[int, int]] = field(default_factory=list)
    missing: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class PairResult:
    kind: str
    idx: int
    ok: bool
    error: str | None = None
    expected: list[list[int]] | None = None
    accepted: list[list[list[int]]] | None = None
    variants: list[VariantResult] = field(default_factory=list)


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
        return all(p.ok for p in self.pairs)


def case_coverage(pairs: list[PairResult]) -> list[str]:
    """Cases silent on some pair. A case is a complete model, so the
    emitted variant set must be the same across all pairs."""
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
    ]


def run_pair(stem: str, task_id: str, kind: str, idx: int, ex) -> PairResult:
    try:
        actuals = run_dl(task_id, ex.input, stem=stem)
        accepted: list[list[list[int]]] = [ex.output]
        if ex.alt is not None and ex.alt.kind == "tiebreak":
            accepted.append(ex.alt.grid)
        variants = [
            VariantResult(
                name=v,
                ok=(g in accepted) and not c and not m,
                actual=g,
                conflicts=c,
                missing=m,
            )
            for v, g, c, m in actuals
        ]
        ok = bool(variants) and all(v.ok for v in variants)
        return PairResult(
            kind=kind,
            idx=idx,
            ok=ok,
            expected=ex.output,
            accepted=accepted,
            variants=variants,
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
