"""The determination plan files under `plan/` of `arclog_convert.out`: one
per solver, with the hash of the inputs it was written from (`inputs_hash`:
the solver file, its task file and its witness file) and the runner and lib
stamp it was written under. A plan file is current where its inputs hash is
the solver's, whatever its runner and lib stamp, and each line over the
enumeration limit gives its cover, which the converter reads;
`--require-current-lib` of `arclog_convert.convert` also requires the current
stamp. A plan file holds the sections of
`scripts/run_dl.py determination-plan` other than the one for the moved
witnesses (`Plan.moved`), which the converter does not read. The plans are
also kept in `store()`, one file per solver and inputs hash, which every
`--out` directory and every worktree shares; a missing or stale plan file is
restored from there, and a current one under `plan/` seeds the store. The
converter reruns the plans that neither holds in worker processes, at most
`engine.pool.pool_size()` at once, each bound to one CPU and taking a chunk of
at most `CHUNK` solvers, then exiting so that none keeps the memory of a
chunk."""

import hashlib
import os
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from arclog_convert import paths
from checker.plan_cache import hash_solver_files
from engine import checkout, rwlock
from engine.memo import write_whole
from engine.pool import pool_size, share_env


PLAN_HASH = "inputs sha256: "

NO_COVER = re.compile(r"  \w+\(\d+\)")
"""A line over the enumeration limit that gives no cover."""

CHUNK = 16
"""The most solvers one worker process takes before it exits. A process
that made 32 plans, the largest among them, peaked at 0.44 GiB."""


def bound_to_one_cpu() -> None:
    """The initializer of a worker: its environment is `share_env(1)`, so the
    Souffle runs it makes in process take a bound of one."""
    os.environ.update(share_env(1))


def inputs_hash(stem: str, solvers: Path) -> str:
    """The hash of the files the plan of the solver `stem` is made from: its
    solver file in the directory `solvers`, its task file and its witness
    file."""
    h = hashlib.sha256()
    hash_solver_files(h, solvers / f"{stem}.dl", stem)
    return h.hexdigest()


def store() -> Path:
    """The directory of the kept plans, under `checkout.cache()`."""
    return checkout.cache() / "plans"


def kept_file(stem: str, digest: str) -> Path:
    """The file in `store()` that holds the plan of the solver `stem` whose
    inputs hash is `digest`."""
    return store() / f"{stem}-{digest[:16]}"


def is_current(text: str, digest: str, lib_line: str | None) -> bool:
    """Whether the plan `text` records the inputs hash `digest`, and, where
    `lib_line` is not None, the runner and lib line `lib_line`, and gives the
    cover of each line over the enumeration limit."""
    lines = text.splitlines()
    return PLAN_HASH + digest in lines and (lib_line is None or lib_line in lines) \
        and not any(NO_COVER.fullmatch(line) for line in lines)


def current_lib_line() -> str:
    """The line of a plan file that records the current runner and lib stamp."""
    from cli.common import stamp
    return f"runner and lib: {stamp()}"


def restore_plans(stems: list[str], lib_line: str | None) -> list[str]:
    """Make `paths.PLANS` hold a current plan file for each of `stems` that
    `store()` or `paths.PLANS` holds one for, and return the others. A plan
    file is current where it records the solver's inputs hash and, where
    `lib_line` is not None, the runner and lib line `lib_line`. A plan file
    under `paths.PLANS` that is current and not in `store()` is added to it.
    Both are written whole or not at all."""
    missing = []
    for stem in stems:
        digest = inputs_hash(stem, paths.SOLVERS)
        mine = paths.PLANS / f"{stem}.txt"
        kept = kept_file(stem, digest)
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
    """Make the determination plan of one solver, without the moved
    witnesses (`cli.survey.plan_output`), and write its lines, the runner and
    lib line `lib_line` and the inputs hash to its file in `store()` and to
    its plan file; None, or the error."""
    from cli.survey import plan_output
    digest = inputs_hash(stem, paths.SOLVERS)
    try:
        code, lines = plan_output(stem, moves=False)
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    if code != 0:
        return lines[-1] if lines else f"exit {code}"
    data = "".join(f"{line}\n" for line in [*lines, lib_line, PLAN_HASH + digest]).encode()
    keep(kept_file(stem, digest), data)
    paths.PLANS.mkdir(parents=True, exist_ok=True)
    write_whole(paths.PLANS / f"{stem}.txt", data)
    return None


def write_chunk(stems: list[str], lib_line: str) -> list[tuple[str, str]]:
    """`write_plan` for each of `stems`, under the shared hold of the heavy
    commands' lock; the stem and error of each plan that failed."""
    with rwlock.held(rwlock.Hold.SHARED):
        failed = []
        for stem in stems:
            err = write_plan(stem, lib_line)
            if err is not None:
                failed.append((stem, err))
        return failed


def chunks(stems: list[str]) -> list[list[str]]:
    """`stems` in chunks of at most `CHUNK`, and of no more than the stems
    per worker that `pool_size()` workers share, so that every worker has
    a chunk; the largest solver files first, so that no long chunk starts
    last."""
    order = sorted(stems, key=lambda stem: -(paths.SOLVERS / f"{stem}.dl").stat().st_size)
    size = min(CHUNK, -(-len(order) // pool_size()))
    return [order[i:i + size] for i in range(0, len(order), size)]


def refresh_plans(stems: list[str], require_current_lib: bool = False) -> None:
    """Make `paths.PLANS` hold a plan file for each of `stems`, and rerun
    those that neither it nor `store()` holds a current one for; where
    `require_current_lib` is set, a plan is current only under the current
    runner and lib line."""
    line = current_lib_line()
    stale = restore_plans(stems, line if require_current_lib else None)
    if not stale:
        return
    print(f"rerunning the determination plan of {len(stale)} solvers")
    with ProcessPoolExecutor(pool_size(), initializer=bound_to_one_cpu, max_tasks_per_child=1) as pool:
        futures = [pool.submit(write_chunk, chunk, line) for chunk in chunks(stale)]
        failed = [pair for future in futures for pair in future.result()]
    for stem, err in sorted(failed):
        print(f"  {stem}: the plan failed: {err}")
