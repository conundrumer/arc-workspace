"""The load and the call of the run scripts the `Op run:` lines an operator
received give, and of the pace script an `Op pace:` line gives, under a time
bound, as `operate.py --help run` and `operate.py --help pace` give
them."""

import json
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import alarms
from controlled_markdown import mctx
from operations import (
    passes,
    runs,
)
from operations.directives import lines
from operations.pacing import Pace, Scripted, Usage
from operations.state import (
    NotComputed,
    Starts,
    State,
    Takes,
)

QUEUE_COMMAND = ("bash", "scripts/queue.sh", "--order", "name", "--all", "--json")


def read_runs(state: State) -> tuple[dict[str, Starts], dict[str, Takes]]:
    """What the script of each `Op run:` line the operator received gave, by
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
    stands = {p: (o.ended, o.standing) for p, o in passes.outcomes(state)}
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
def bounded(seconds: int, calls: str) -> Iterator[None]:
    """Raise `ScriptTimeout` in the block once `seconds` have passed, with
    `calls` the calls the block makes."""
    def expire() -> None:
        raise ScriptTimeout(mctx("the load and {calls} ran past "
                                 "{seconds} seconds").format(calls=calls, seconds=seconds))
    alarm = alarms.Alarm(expire)
    alarm.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        alarm.clear()


def fault_text(e: BaseException) -> str:
    return "".join(traceback.format_exception_only(e)).strip()


def module_name(path: Path) -> str:
    return f"run_script_{abs(hash((str(path), time.time())))}"


def load(path: Path, name: str) -> ModuleType:
    """The script at `path`, loaded afresh as the module `name`, which
    stays in `sys.modules` until its caller pops it."""
    # Compiled from its text at each read: a cached bytecode file
    # hides an edit that keeps the file's size within one second.
    loading = ModuleType(name)
    loading.__file__ = str(path)
    sys.modules[name] = loading
    exec(compile(path.read_text(), str(path), "exec"), loading.__dict__)
    return loading


def pace_reads(path: Path, usage: Usage) -> Pace:
    """What the pace script at `path`, loaded afresh as a module, gives
    from its `paces` called with `usage`, within `runs.SCRIPT_SECONDS`."""
    name = module_name(path)
    try:
        with bounded(runs.SCRIPT_SECONDS, mctx("the call of `paces`")):
            given = load(path, name).paces(usage)
    except (Exception, SystemExit) as e:
        return NotComputed(fault_text(e))
    finally:
        sys.modules.pop(name, None)
    if not isinstance(given, bool):
        return NotComputed(mctx("`paces` gave {given}, no `bool`").format(given=repr(given)))
    return Scripted(path, given)


def entry_read[T](read: Callable[[], T]) -> T | str:
    """What `read`, a call of an entry point of a run script, gives, or the
    text of its fault."""
    try:
        return read()
    except ScriptTimeout:
        raise
    except (Exception, SystemExit) as e:
        return fault_text(e)


def script_reads(path: Path, run: runs.Run,
                 tickets: Callable[[], tuple[runs.RunTicket, ...]]) -> tuple[Starts, Takes]:
    """What the run script at `path`, loaded afresh as a module, gives from
    its `starts` called with `run`, and from its `takes` called on each of
    `tickets`, or None where it defines no `takes`, each as the text of its
    fault where it has one, within `runs.SCRIPT_SECONDS`. A fault of the
    load or of the bound is the fault of both, unless the loaded module
    defines no `takes`."""
    name = module_name(path)
    module: ModuleType | None = None
    try:
        with bounded(runs.SCRIPT_SECONDS, mctx("the calls of `starts` and `takes`")):
            module = loaded = load(path, name)
            starts = entry_read(lambda: runs.read_starts(loaded.starts(run)))
            takes = getattr(module, "takes", None)
            return starts, None if takes is None else entry_read(
                lambda: runs.read_takes(takes, tickets()))
    except (Exception, SystemExit) as e:
        fault = fault_text(e)
        return fault, (None if module is not None and not hasattr(module, "takes") else fault)
    finally:
        sys.modules.pop(name, None)
