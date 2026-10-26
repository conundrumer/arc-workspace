"""The determination plan files under `plan/` of `arclog_convert.out`: one
per solver, from `scripts/run_dl.py determination-plan`, with the hash of the
solver file and the runner and lib stamp it was written under. The plans are
also kept in `store()`, one file per solver, runner and lib state, which every
`--out` directory and every worktree shares; a missing or stale plan file is
restored from there, and an up-to-date one under `plan/` seeds the store. The
converter reruns a plan that neither holds, on at most
`engine.pool.pool_size()` threads, each running its command bounded to one
CPU."""

import hashlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from arclog_convert import paths
from engine import checkout
from engine.memo import write_whole
from engine.pool import pool_size, share_env


PLAN_HASH = "solver file sha256: "


def solver_hash(stem: str) -> str:
    return hashlib.sha256((paths.SOLVERS / f"{stem}.dl").read_bytes()).hexdigest()


def store() -> Path:
    """The directory of the kept plans, under `checkout.cache()`."""
    return checkout.cache() / "plans"


def kept_file(stem: str, digest: str, lib_line: str) -> Path:
    """The file in `store()` that holds the plan of the solver `stem` whose
    file hash is `digest`, under the runner and lib line `lib_line`."""
    key = hashlib.sha256(f"{digest}\0{lib_line}".encode()).hexdigest()[:16]
    return store() / f"{stem}-{key}"


def is_current(text: str, digest: str, lib_line: str) -> bool:
    """Whether the plan `text` records the solver file hash `digest` and the
    runner and lib line `lib_line`."""
    lines = text.splitlines()
    return PLAN_HASH + digest in lines and lib_line in lines


def current_lib_line() -> str:
    """The line of a plan file that records the current runner and lib stamp."""
    from cli.common import stamp
    return f"runner and lib: {stamp()}"


def restore_plans(stems: list[str], lib_line: str) -> list[str]:
    """Make `paths.PLANS` hold a plan file up to date under the runner and
    lib line `lib_line` for each of `stems` that `store()` or `paths.PLANS`
    holds one for, and return the others. A plan file under `paths.PLANS`
    that is up to date and not in `store()` is added to it. Both are
    written whole or not at all."""
    missing = []
    for stem in stems:
        digest = solver_hash(stem)
        mine = paths.PLANS / f"{stem}.txt"
        kept = kept_file(stem, digest, lib_line)
        if mine.exists() and is_current(mine.read_text(), digest, lib_line):
            if not kept.exists():
                keep(kept, mine.read_bytes())
        elif kept.exists() and is_current(kept.read_text(), digest, lib_line):
            paths.PLANS.mkdir(parents=True, exist_ok=True)
            write_whole(mine, kept.read_bytes())
        else:
            missing.append(stem)
    return missing


def keep(kept: Path, data: bytes) -> None:
    """Write `data` whole to the file `kept` in `store()`."""
    kept.parent.mkdir(parents=True, exist_ok=True)
    write_whole(kept, data)


def write_plan(stem: str, lib_line: str) -> str | None:
    """Run the determination plan of one solver and write its output, with
    the solver file's hash, to its file in `store()` (under the runner and
    lib line `lib_line`) and to its plan file; None, or the error."""
    digest = solver_hash(stem)
    r = subprocess.run([sys.executable, str(paths.ROOT / "scripts" / "run_dl.py"), "determination-plan", stem],
                       cwd=paths.ROOT, capture_output=True, text=True, env=share_env(1))
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        return lines[-1] if lines else f"exit {r.returncode}"
    text = r.stdout + r.stderr
    data = (text + ("" if text.endswith("\n") else "\n") + PLAN_HASH + digest + "\n").encode()
    keep(kept_file(stem, digest, lib_line), data)
    paths.PLANS.mkdir(parents=True, exist_ok=True)
    write_whole(paths.PLANS / f"{stem}.txt", data)
    return None


def refresh_plans(stems: list[str]) -> None:
    line = current_lib_line()
    stale = restore_plans(stems, line)
    if not stale:
        return
    print(f"rerunning the determination plan of {len(stale)} solvers")
    with ThreadPoolExecutor(max_workers=pool_size()) as pool:
        for stem, err in zip(stale, pool.map(lambda stem: write_plan(stem, line), stale)):
            if err is not None:
                print(f"  {stem}: the plan failed: {err}")
