"""The calls of a run that run in the background, the time each ended,
and whether one may still run, with the read of the files a running
process holds open. `may_still_run` is kept on disk
(`state_reads.Kept.DISK`) in this module, which imports none of the
modules that call it, so that a commit to those leaves its records
standing (`kept_reads.code_of`)."""

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from noted_reads import note_live, note_read
from command_labels import AGENT_TOOLS
from run_reads import (BACKGROUND_TASK, LaunchStatus, blocks, in_background, notified,
                       output_file, run_entries, tool_calls)
from file_reads import is_file, mtime, resolved
from state_reads import DERIVED, Kept, state_cache
from transcript_entries import epoch
from transcript_snapshots import Entry, Refused

# The keys of a call's result that give an id a notification of the call
# gives.
TASK_KEYS = (BACKGROUND_TASK, "taskId", "agentId")


@dataclass(frozen=True)
class Background:
    """A call whose result says it runs in the background: the ids a
    notification of it gives, its tool-use id among them, and for a Bash
    call, the output file its result names, or None where it names none."""
    ids: frozenset[str]
    output: Path | None


def backgrounds(entries: Iterable[Entry], agent_calls: set[str],
                undecided: list[str]) -> dict[str, Background]:
    """Each call among `entries` that runs in the background, by its
    tool-use id, where `agent_calls` are the tool-use ids of Agent calls."""
    out: dict[str, Background] = {}
    for e in entries:
        r = e.get("toolUseResult")
        if e.get("type") != "user" or not isinstance(r, dict):
            continue
        bash = bool(r.get(BACKGROUND_TASK))
        for b in blocks(e, "tool_result"):
            if not b.get("tool_use_id"):
                continue
            call = str(b["tool_use_id"])
            if bash or (call in agent_calls and in_background(r, undecided, call)):
                out[call] = Background(
                    frozenset({call, *(str(r[k]) for k in TASK_KEYS if r.get(k))}),
                    output_file(b) if bash else None)
    return out


def background_ends(found: dict[str, Background],
                    entries: Iterable[Entry]) -> dict[str, float | None]:
    """When each call of `found` ended, as `profile_runs.py --help runs`
    gives it, from the notifications among `entries`, or None where it still runs
    or whether it runs is unknown."""
    entries_list = list(entries)
    told: dict[str, float] = {}
    for e in entries_list:
        if e.get("type") != "assistant" and e.get("timestamp"):
            t = epoch(e["timestamp"])
            for ident in notified(e):
                told[ident] = min(t, told.get(ident, t))
    last = max((epoch(e["timestamp"]) for e in entries_list if e.get("timestamp")),
               default=0.0)
    ends: dict[str, float | None] = {
        call: min((told[i] for i in b.ids if i in told), default=None)
        for call, b in found.items()}
    outputs = {call: b.output for call, b in found.items()
               if ends[call] is None and b.output is not None}
    for f in outputs.values():
        note_read(f)
    files = {call: f for call, f in outputs.items() if is_file(f)}
    for call, f in files.items():
        if str(resolved(f)) in open_files().paths:
            note_live()
            continue
        try:
            ends[call] = mtime(f)
        except FileNotFoundError:
            pass
    for call, f in outputs.items():
        if call in files:
            continue
        if str(resolved(f)) in open_files().gone:
            note_live()
        else:
            ends[call] = last
    return ends


@dataclass(frozen=True)
class OpenFiles:
    """The paths of the files a process holds open, as `lsof` gives them,
    and those of them with no link (`gone`)."""
    paths: frozenset[str]
    gone: frozenset[str]


@state_cache(None)
def open_files() -> OpenFiles:
    """The files processes hold open, read once for each state, so each
    reader of a run sees one state, and one `lsof` call serves every run;
    refused where `lsof` writes to stderr."""
    # lsof exits 1 where it finds no open file as well as on a fault, so
    # only its stderr tells a fault.
    out = subprocess.run(["lsof", "-n", "-P", "+L", "-F", "nk"], capture_output=True, text=True)
    if out.stderr.strip():
        raise Refused(mctx("which files a process holds open is unknown: lsof says {err}").format(
            err=out.stderr.strip()))
    paths: set[str] = set()
    gone: set[str] = set()
    links: str | None = None
    for line in out.stdout.splitlines():
        if line.startswith("f"):
            links = None
        elif line.startswith("k"):
            links = line[1:]
        elif line.startswith("n"):
            paths.add(line[1:])
            if links == "0":
                gone.add(line[1:])
    return OpenFiles(frozenset(paths), frozenset(gone))


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def may_still_run(path: Path, reached: frozenset[str], undecided: list[str]) -> bool:
    """Whether a call the run at `path` backgrounded, other than a call of
    `reached`, may still run. Only the lines that name such a call or its
    ids are read, which spares `profile` the whole run where none still
    runs."""
    results = list(run_entries(path, {BACKGROUND_TASK, LaunchStatus.ASYNC_LAUNCHED.value}))
    calls = {str(b["tool_use_id"]) for e in results for b in blocks(e, "tool_result")
             if b.get("tool_use_id")} - reached
    if not calls:
        return False
    found = {c: b for c, b in backgrounds(results, tool_calls(run_entries(path, calls), AGENT_TOOLS),
                                          undecided).items() if c in calls}
    if not found:
        return False
    ids = set().union(*(b.ids for b in found.values()))
    return None in background_ends(found, run_entries(path, ids)).values()
