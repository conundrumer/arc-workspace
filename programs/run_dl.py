"""Run Souffle solvers against their tasks' train+test pairs.

Usage:
    uv run python programs/run_dl.py            # run all .dl solvers
    uv run python programs/run_dl.py <stem>     # run one

For a single stem, encodes each example's input grid as fact lines on stdin,
invokes `souffle -D- <stem>.dl`, reads the output relation from stdout,
compares to expected output grid.
"""

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from arc.task import load as load_task  # noqa: E402

SOLVERS_DIR = REPO_ROOT / "programs" / "solvers"


def grid_to_facts(rows: list[list[int]]) -> str:
    """Encode a grid as Souffle facts for `in(p, col)` over Position records."""
    h = len(rows)
    w = len(rows[0]) if h > 0 else 0
    lines = []
    for row in range(h):
        for col in range(w):
            t = row
            b = h - 1 - row
            l = col
            r = w - 1 - col
            lines.append(f"[{t}, {b}, {l}, {r}]\t{rows[row][col]}")
    return "\n".join(lines) + ("\n" if lines else "")


def parse_output(stdout: str) -> list[list[list[int]]]:
    """Parse Souffle's default text output for the `out` relation.

    Returns a list of candidate grids. If `out` has an extra trailing
    integer column (a choice id), cells are grouped by it and each group
    becomes one candidate.
    """
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    if not data:
        return [[]]

    line_re = re.compile(r"\[(-?\d+), (-?\d+), (-?\d+), (-?\d+)\]\t(-?\d+)(?:\t(.+))?$")
    grouped: dict[str, list] = {}
    for line in data.splitlines():
        m = line_re.match(line)
        if not m:
            raise ValueError(f"unexpected fact line: {line!r}")
        groups = m.groups()
        cid = groups[5] if groups[5] is not None else ""
        cells = grouped.setdefault(cid, [])
        cells.append(tuple(int(x) for x in groups[:5]))

    candidates: list[list[list[int]]] = []
    for cid in sorted(grouped):
        cells = grouped[cid]
        bounds = {(t + b + 1, l + r + 1) for (t, b, l, r, _) in cells}
        if len(bounds) != 1:
            raise ValueError(f"inconsistent grid bounds in choice {cid}: {bounds}")
        h, w = next(iter(bounds))
        grid = [[0] * w for _ in range(h)]
        for (t, b, l, r, color) in cells:
            if t < 0 or l < 0 or t >= h or l >= w:
                raise ValueError(f"cell out of derived bounds: ({t}, {l}) in {h}x{w}")
            grid[t][l] = color
        candidates.append(grid)
    return candidates


def run_dl(task_id: str, input_rows: list[list[int]], stem: str | None = None) -> list[list[list[int]]]:
    dl_path = SOLVERS_DIR / f"{stem or task_id}.dl"
    if not dl_path.exists():
        raise FileNotFoundError(f"no .dl solver at {dl_path}")
    facts = grid_to_facts(input_rows)
    result = subprocess.run(
        ["souffle", "-D-", "-w", str(dl_path)],
        input=facts,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"souffle exited {result.returncode}:\n{result.stderr}")
    return parse_output(result.stdout)


@dataclass
class PairResult:
    kind: str
    idx: int
    ok: bool
    detail: str | None


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


def run_task(stem: str) -> TaskResult:
    task_id = stem.split("_", 1)[0]
    task = load_task(task_id)
    result = TaskResult(stem=stem)
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            try:
                actuals = run_dl(task_id, ex.input, stem=stem)
                accepted = [ex.output]
                if ex.alt is not None and ex.alt.kind == "tiebreak":
                    accepted.append(ex.alt.grid)
                ok = bool(actuals) and all(a in accepted for a in actuals)
                detail = None if ok else f"expected each in {accepted}\n      actuals  {actuals}"
            except Exception as e:
                ok = False
                detail = f"{type(e).__name__}: {e}"
            result.pairs.append(PairResult(kind=kind, idx=idx, ok=ok, detail=detail))
    return result


def all_stems() -> list[str]:
    return sorted(p.stem for p in SOLVERS_DIR.glob("*.dl"))


def cmd_one(stem: str) -> int:
    result = run_task(stem)
    for p in result.pairs:
        print(f"{p.kind}[{p.idx}]: {'PASS' if p.ok else 'FAIL'}")
        if p.detail:
            print(f"  {p.detail}")
    return 0 if result.all_pass else 1


def cmd_all() -> int:
    results = [run_task(stem) for stem in all_stems()]
    for r in results:
        marker = "PASS" if r.all_pass else "FAIL"
        print(f"{r.stem}: {r.passes}/{r.total} {marker}")

    failed = [r for r in results if not r.all_pass]
    if failed:
        print()
        print(f"--- {len(failed)} failing solver(s) ---")
        for r in failed:
            print(f"\n{r.stem}:")
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
    print(f"usage: {sys.argv[0]} [<task_id_or_stem>]", file=sys.stderr)
    sys.exit(2)
