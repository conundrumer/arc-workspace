"""The load and the call of the run scripts the `Run:` lines an operator
received give, under a time bound, as `operate.py --help run` gives them."""

import json
import signal
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType, ModuleType

from controlled_markdown import mctx
from operations import (
    passes,
    runs,
)
from operations.directives import lines
from operations.state import (
    Starts,
    State,
    Takes,
)

QUEUE_COMMAND = ("bash", "scripts/queue.sh", "--order", "name", "--all", "--json")


def read_runs(state: State) -> tuple[dict[str, Starts], dict[str, Takes]]:
    """What the script of each `Run:` line the operator received gave, by
    its run, where it received one, with the queue's full listing: from its
    `starts`, and from its `takes`. Where the listing fails, its failure is
    the fault of each such line, for both."""
    given = runs.run_lines(lines(state))
    if not given:
        return {}, {}
    listed = subprocess.run(QUEUE_COMMAND, cwd=state.main_tree, capture_output=True, text=True)
    if listed.returncode != 0:
        fault = mctx("the queue's listing `{command}` exited {code}: {stderr}").format(
            command=" ".join(QUEUE_COMMAND), code=listed.returncode, stderr=listed.stderr.strip())
        return {runs.run_id(ln): fault for ln in given}, {runs.run_id(ln): fault for ln in given}
    queue = tuple(e["id"] for e in json.loads(listed.stdout))
    stands = dict(passes.outcomes(state))
    starts: dict[str, Starts] = {}
    takes: dict[str, Takes] = {}
    for ln in given:
        run = runs.view(state, queue, ln, stands)
        starts[runs.run_id(ln)], takes[runs.run_id(ln)] = script_reads(
            runs.script_path(state.main_tree, ln), run, lambda: runs.run_tickets(state, run))
    return starts, takes


class ScriptTimeout(Exception):
    pass


@contextmanager
def bounded(seconds: int) -> Iterator[None]:
    """Raise `ScriptTimeout` in the block once `seconds` have passed."""
    def expire(_signum: int, _frame: FrameType | None) -> None:
        raise ScriptTimeout(mctx("the load and the calls of `starts` and `takes` ran past "
                                 "{seconds} seconds").format(seconds=seconds))
    before = signal.signal(signal.SIGALRM, expire)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, before)


def fault_text(e: BaseException) -> str:
    return "".join(traceback.format_exception_only(e)).strip()


def script_reads(path: Path, run: runs.Run,
                 tickets: Callable[[], tuple[runs.RunTicket, ...]]) -> tuple[Starts, Takes]:
    """What the run script at `path`, loaded afresh as a module, gives from
    its `starts` called with `run`, and from its `takes` called on each of
    `tickets`, or None where it defines no `takes`, each as the text of its
    fault where it has one, within `runs.SCRIPT_SECONDS`. A fault of the
    load or of the bound is the fault of both, unless the loaded module
    defines no `takes`."""
    name = f"run_script_{abs(hash((str(path), time.time())))}"
    module: ModuleType | None = None
    try:
        with bounded(runs.SCRIPT_SECONDS):
            # Compiled from its text at each read: a cached bytecode file
            # hides an edit that keeps the file's size within one second.
            loading = ModuleType(name)
            loading.__file__ = str(path)
            sys.modules[name] = loading
            exec(compile(path.read_text(), str(path), "exec"), loading.__dict__)
            module = loading
            try:
                starts = runs.read_starts(module.starts(run))
            except ScriptTimeout:
                raise
            except (Exception, SystemExit) as e:
                starts = fault_text(e)
            takes = getattr(module, "takes", None)
            if takes is None:
                return starts, None
            try:
                return starts, runs.read_takes(takes, tickets())
            except ScriptTimeout:
                raise
            except (Exception, SystemExit) as e:
                return starts, fault_text(e)
    except (Exception, SystemExit) as e:
        fault = fault_text(e)
        return fault, (None if module is not None and not hasattr(module, "takes") else fault)
    finally:
        sys.modules.pop(name, None)
