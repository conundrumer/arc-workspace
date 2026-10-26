"""The determination plan files under `plan/` of `arclog_convert.out`: one
per solver, from `scripts/run_dl.py determination-plan`, with the hash of the
solver file and the runner and lib stamp it was written under. The converter
reads them and reruns a stale one."""

import hashlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from arclog_convert import paths


PLAN_HASH = "solver file sha256: "


def solver_hash(stem: str) -> str:
    return hashlib.sha256((paths.SOLVERS / f"{stem}.dl").read_bytes()).hexdigest()


def stale_plans(stems: list[str]) -> list[str]:
    """The solvers whose plan file is missing, or records a hash other than
    their solver file's, or a runner and lib stamp other than the current
    one."""
    from cli.common import stamp
    lib_line = f"runner and lib: {stamp()}"
    out = []
    for stem in stems:
        p = paths.PLANS / f"{stem}.txt"
        lines = p.read_text().splitlines() if p.exists() else []
        if PLAN_HASH + solver_hash(stem) not in lines or lib_line not in lines:
            out.append(stem)
    return out


def write_plan(stem: str) -> str | None:
    """Run the determination plan of one solver and write its output, with
    the solver file's hash, to its plan file; None, or the error."""
    digest = solver_hash(stem)
    r = subprocess.run([sys.executable, str(paths.ROOT / "scripts" / "run_dl.py"), "determination-plan", stem],
                       cwd=paths.ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        return lines[-1] if lines else f"exit {r.returncode}"
    text = r.stdout + r.stderr
    paths.PLANS.mkdir(parents=True, exist_ok=True)
    (paths.PLANS / f"{stem}.txt").write_text(text + ("" if text.endswith("\n") else "\n") + PLAN_HASH + digest + "\n")
    return None


def refresh_plans(stems: list[str]) -> None:
    stale = stale_plans(stems)
    if not stale:
        return
    print(f"rerunning the determination plan of {len(stale)} solvers")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for stem, err in zip(stale, pool.map(write_plan, stale)):
            if err is not None:
                print(f"  {stem}: the plan failed: {err}")
