"""Run a Souffle solver against its task's train+test pairs.

Usage:
    uv run python programs/run_dl.py <task_id>

Loads programs/solvers/<task_id>.dl, encodes each example's input grid as
fact lines on stdin, invokes `souffle -D- <task.dl>`, reads the output
relation from stdout, compares to expected output grid.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
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


def parse_output(stdout: str) -> list[list[int]]:
    """Parse Souffle's default text output for the `out` relation."""
    parts = re.split(r"^={3,}$", stdout, flags=re.MULTILINE)
    if len(parts) < 3:
        raise ValueError(f"unexpected souffle output:\n{stdout}")
    data = parts[1].strip()
    if not data:
        return []

    cells = []
    line_re = re.compile(r"\[(-?\d+), (-?\d+), (-?\d+), (-?\d+)\]\t(-?\d+)")
    for line in data.splitlines():
        m = line_re.match(line)
        if not m:
            raise ValueError(f"unexpected fact line: {line!r}")
        cells.append(tuple(int(x) for x in m.groups()))

    bounds = {(t + b + 1, l + r + 1) for (t, b, l, r, _) in cells}
    if len(bounds) != 1:
        raise ValueError(f"inconsistent grid bounds across cells: {bounds}")
    h, w = next(iter(bounds))
    out = [[0] * w for _ in range(h)]
    for (t, b, l, r, color) in cells:
        if t < 0 or l < 0 or t >= h or l >= w:
            raise ValueError(f"cell out of derived bounds: ({t}, {l}) in {h}x{w}")
        out[t][l] = color
    return out


def run_dl(task_id: str, input_rows: list[list[int]], stem: str | None = None) -> list[list[int]]:
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


def run_one(stem: str) -> int:
    task_id = stem.split("_", 1)[0]
    task = load_task(task_id)
    pairs: list[PairResult] = []
    for kind, examples in (("train", task.train), ("test", task.test)):
        for idx, ex in enumerate(examples):
            try:
                actual = run_dl(task_id, ex.input, stem=stem)
                accepted = [ex.output]
                if ex.alt is not None and ex.alt.kind == "tiebreak":
                    accepted.append(ex.alt.grid)
                ok = actual in accepted
                detail = None if ok else f"expected one of {accepted}\n      actual   {actual}"
            except Exception as e:
                ok = False
                detail = f"{type(e).__name__}: {e}"
            pairs.append(PairResult(kind=kind, idx=idx, ok=ok, detail=detail))

    for p in pairs:
        print(f"{p.kind}[{p.idx}]: {'PASS' if p.ok else 'FAIL'}")
        if p.detail:
            print(f"  {p.detail}")
    return 0 if all(p.ok for p in pairs) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <task_id_or_stem>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run_one(sys.argv[1]))
