"""Run a solver against its task's train+test pairs.

Usage:
    uv run python programs/run.py              # run every solver
    uv run python programs/run.py <task_id>    # run one solver

Loads programs/solvers/<task_id>.py via importlib (task IDs starting with
digits aren't valid Python identifiers, so plain `import` is out). The
solver module must expose `solve(grid, c)` and a module-level `CONSTS`.
"""

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arc.task import load as load_task  # noqa: E402
from programs.lib import from_relational, to_relational  # noqa: E402

SOLVERS_DIR = REPO_ROOT / "programs" / "solvers"


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


def run_one(task_id: str) -> TaskResult:
    solver = load_solver(task_id)
    task = load_task(task_id)
    pairs: list[PairResult] = []
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            try:
                actual = from_relational(solver.solve(to_relational(ex.input), solver.CONSTS))
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

    total_pass = sum(r.passes for r in results)
    total_pairs = sum(r.total for r in results)
    print()
    print(
        f"summary: {len(results) - len(failed)}/{len(results)} solvers, "
        f"{total_pass}/{total_pairs} pairs"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(cmd_all())
    if len(sys.argv) == 2:
        sys.exit(cmd_one(sys.argv[1]))
    print(f"usage: {sys.argv[0]} [<task_id>]", file=sys.stderr)
    sys.exit(2)
