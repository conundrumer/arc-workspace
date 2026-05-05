"""Run a solver against its task's train+test pairs.

Usage:
    uv run python programs/run.py              # run every solver
    uv run python programs/run.py <task_id>    # run one solver

Loads programs/solvers/<task_id>.py via importlib (task IDs starting with
digits aren't valid Python identifiers, so plain `import` is out). The
solver module must expose `solve(grid, c)` and a module-level `CONSTS`.

Tiebreak solvers take a third arg `choice: ChoiceFn` and call `choice(s)`
on a frozenset of options. The framework discovers the choice points in
one pass, then enumerates the cartesian product of branches; for examples
with `kind: "tiebreak"` alts, the union of branch outputs must equal
{base, alt} (set equality — full coverage required).
"""

import importlib.util
import inspect
import itertools
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arc.task import load as load_task  # noqa: E402
from programs.lib import Color, Grid  # noqa: E402

SOLVERS_DIR = REPO_ROOT / "programs" / "solvers"


def to_relational(rows: list[list[int]]) -> Grid:
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    return {
        ((r, w - 1 - c, h - 1 - r, c), Color(rows[r][c]))
        for r in range(h)
        for c in range(w)
    }


def from_relational(g: Grid) -> list[list[int]]:
    if not g:
        return []
    bounds = {(t + b + 1, l + r + 1) for ((t, r, b, l), _) in g}
    if len(bounds) != 1:
        raise ValueError(f"inconsistent grid bounds across positions: {bounds}")
    h, w = next(iter(bounds))
    by_cell: dict[tuple[int, int], int] = {}
    for (t, r, b, l), col in g:
        if t < 0 or r < 0 or b < 0 or l < 0:
            raise ValueError(f"negative position component: ({t}, {r}, {b}, {l})")
        if (t, l) in by_cell:
            raise ValueError(
                f"duplicate cell at (top={t}, left={l}): "
                f"Color({by_cell[(t, l)]}) and Color({col.value})"
            )
        by_cell[(t, l)] = col.value
    if len(by_cell) != h * w:
        raise ValueError(f"coverage: {len(by_cell)} cells, expected {h * w} for {h}x{w}")
    out = [[0] * w for _ in range(h)]
    for (t, l), v in by_cell.items():
        out[t][l] = v
    return out


@dataclass
class PairResult:
    kind: str
    idx: int
    ok: bool
    detail: str | None  # populated only on failure


@dataclass
class TaskResult:
    task_id: str
    pairs: list[PairResult]

    @property
    def passes(self) -> int:
        return sum(1 for p in self.pairs if p.ok)

    @property
    def total(self) -> int:
        return len(self.pairs)

    @property
    def all_pass(self) -> bool:
        return all(p.ok for p in self.pairs)


def load_solver(task_id: str) -> ModuleType:
    path = SOLVERS_DIR / f"{task_id}.py"
    if not path.exists():
        raise FileNotFoundError(f"no solver at {path}")
    spec = importlib.util.spec_from_file_location(f"solver_{task_id}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _branches(solve_fn: Callable, grid: Any, c: Any) -> list[Any]:
    """Run solve_fn over its choice domain.

    Single-branch (no `choice` param) returns [solve(grid, c)]. Tiebreak
    solvers (with `choice: ChoiceFn`) get a discovery run that records
    every `choice(s)` call's set, then a replay run per element of the
    cartesian product across choice points.
    """
    if "choice" not in inspect.signature(solve_fn).parameters:
        return [solve_fn(grid, c)]

    recorded: list[tuple] = []

    def discover(s):
        t = tuple(s)
        recorded.append(t)
        return t[0]

    solve_fn(grid, c, choice=discover)

    outs: list[Any] = []
    for picks in itertools.product(*recorded):
        it = iter(picks)
        outs.append(solve_fn(grid, c, choice=lambda _s, _it=it: next(_it)))
    return outs


def _hashable(g: list[list[int]]) -> tuple:
    return tuple(tuple(row) for row in g)


def run_one(task_id: str) -> TaskResult:
    solver = load_solver(task_id)
    task = load_task(task_id)
    pairs: list[PairResult] = []
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            try:
                grid = to_relational(ex.input)
                actual_grids = [from_relational(g) for g in _branches(solver.solve, grid, solver.CONSTS)]

                if ex.alt and ex.alt.kind == "tiebreak":
                    actual_set = {_hashable(g) for g in actual_grids}
                    expected_set = {_hashable(ex.output), _hashable(ex.alt.grid)}
                    ok = actual_set == expected_set
                    detail = (
                        None if ok
                        else f"expected branches {sorted(expected_set)}\n      actual branches  {sorted(actual_set)}"
                    )
                else:
                    if len(actual_grids) != 1:
                        ok = False
                        detail = f"got {len(actual_grids)} branches but example has no tiebreak alt"
                    else:
                        actual = actual_grids[0]
                        ok = actual == ex.output
                        detail = None if ok else f"expected {ex.output}\n      actual   {actual}"
            except Exception as e:
                ok = False
                detail = f"{type(e).__name__}: {e}"
            pairs.append(PairResult(kind=kind, idx=idx, ok=ok, detail=detail))
    return TaskResult(task_id=task_id, pairs=pairs)


def all_task_ids() -> list[str]:
    return sorted(p.stem for p in SOLVERS_DIR.glob("*.py") if not p.stem.startswith("_"))


def cmd_one(task_id: str) -> int:
    result = run_one(task_id)
    for p in result.pairs:
        print(f"{p.kind}[{p.idx}]: {'PASS' if p.ok else 'FAIL'}")
        if p.detail:
            print(f"  {p.detail}")
    return 0 if result.all_pass else 1


def cmd_all() -> int:
    results = [run_one(tid) for tid in all_task_ids()]
    for r in results:
        marker = "PASS" if r.all_pass else "FAIL"
        print(f"{r.task_id}: {r.passes}/{r.total} {marker}")

    failed = [r for r in results if not r.all_pass]
    if failed:
        print()
        print(f"--- {len(failed)} failing solver(s) ---")
        for r in failed:
            print(f"\n{r.task_id}:")
            for p in r.pairs:
                if not p.ok:
                    print(f"  {p.kind}[{p.idx}]: {p.detail}")

    print()
    print(f"summary: {len(results) - len(failed)}/{len(results)} solvers")
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(cmd_all())
    if len(sys.argv) == 2:
        sys.exit(cmd_one(sys.argv[1]))
    print(f"usage: {sys.argv[0]} [<task_id>]", file=sys.stderr)
    sys.exit(2)
