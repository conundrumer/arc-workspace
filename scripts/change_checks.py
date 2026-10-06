"""The checks `merge_change.py` runs on a change: the commands, the paths
that call for the code checks, and the runs of the checks in a tree."""

import contextlib
import subprocess
import sys
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from cli.common import SOURCES
from controlled_markdown import mctx
from engine import checkout, duration

CODE_DIRS = ("src", "scripts", "tests", "data/tasks")
"""The directories a change under which runs the code checks."""

CODE_FILES = ("pyproject.toml", "uv.lock")
"""The files that set the environment every code check runs in."""

TAIL = 40
"""Lines of a failed command's output a refusal shows."""


@dataclass(frozen=True)
class Check:
    argv: tuple[str, ...]


def said(done: subprocess.CompletedProcess[str]) -> str:
    """What a command wrote, its last `TAIL` lines."""
    lines = (done.stdout + done.stderr).strip().splitlines()
    return "\n".join(lines[-TAIL:]) or f"exit status {done.returncode}"


MARKDOWN_CHECK = Check(("uv", "run", "python", "-m", "controlled_markdown", "check"))
"""The check every change runs."""


def code_paths(tree: Path, main: Path, touched: set[str]) -> set[str]:
    """The paths of `touched` whose content the results of pyright and
    pytest can depend on. A path `SOURCES` matches is found in `tree`, where the
    change adds or edits it, or in the main worktree `main`, where the
    change deletes it."""
    sources = {str(p.relative_to(root)) for root in (tree, main)
               for pattern in SOURCES for p in root.glob(pattern)}
    return {p for p in touched
            if p in CODE_FILES or p in sources
            or any(p.startswith(f"{d}/") for d in CODE_DIRS)}


def run_in(tree: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """A `uv run` command in `tree`, in that tree's own environment."""
    return subprocess.run(list(argv), cwd=tree, env=checkout.tree_env(), capture_output=True,
                          text=True)


def timed(step: str) -> contextlib.AbstractContextManager[None]:
    """A step of `merge_change.py`, which writes its step line
    (`engine.duration.STEP`) as it ends."""
    return duration.step("merge_change", step)


def run_check(tree: Path, argv: Sequence[str], shown: str) -> subprocess.CompletedProcess[str]:
    """A check run as `run_in` runs a command, each line it writes on stderr
    written on this script's stderr as it comes, timed as the step
    `shown`."""
    with timed(shown):
        proc = subprocess.Popen(list(argv), cwd=tree, env=checkout.tree_env(), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        assert proc.stdout is not None and proc.stderr is not None
        stdout = proc.stdout
        out: list[str] = []
        reader = threading.Thread(target=lambda: out.append(stdout.read()))
        reader.start()
        err: list[str] = []
        for line in proc.stderr:
            print(line, end="", file=sys.stderr, flush=True)
            err.append(line)
        reader.join()
        return subprocess.CompletedProcess(list(argv), proc.wait(), "".join(out), "".join(err))


def failures(tree: Path, checks: Sequence[Check]) -> list[str]:
    """Run `checks` in `tree` concurrently: the output of each that fails."""
    shown = [" ".join(c.argv) for c in checks]
    for s in shown:
        print(mctx("merge_change: running {s}").format(s=s), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, len(checks))) as pool:
        dones = list(pool.map(lambda c, s: run_check(tree, c.argv, s), checks, shown))
    return [mctx("the check `{s}` failed:").format(s=s) + "\n" + said(done)
            for s, done in zip(shown, dones, strict=True) if done.returncode != 0]
