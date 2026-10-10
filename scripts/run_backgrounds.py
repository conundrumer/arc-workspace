"""The calls of a run that run in the background, and the time each
ended, with the read of the files a running process holds open."""

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from noted_reads import note_live, note_read
from run_reads import BACKGROUND_TASK, blocks, in_background, notified, output_file
from transcripts import Entry, Refused, epoch, state_cache


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
    """When each call of `found` ended, as the HELP of `profile_runs` gives
    it, from the notifications among `entries`, or None where it still runs
    or whether it runs is unknown."""
    told: dict[str, float] = {}
    for e in entries:
        if e.get("type") != "assistant" and e.get("timestamp"):
            t = epoch(e["timestamp"])
            for ident in notified(e):
                told[ident] = min(t, told.get(ident, t))
    ends: dict[str, float | None] = {
        call: min((told[i] for i in b.ids if i in told), default=None)
        for call, b in found.items()}
    outputs = {call: b.output for call, b in found.items()
               if ends[call] is None and b.output is not None}
    for f in outputs.values():
        note_read(f)
    files = {call: f for call, f in outputs.items() if f.is_file()}
    for call, f in files.items():
        if str(f.resolve()) in held_in(f.resolve().parent):
            note_live()
            continue
        try:
            ends[call] = f.stat().st_mtime
        except FileNotFoundError:
            pass
    return ends


@state_cache(None)
def held_in(directory: Path) -> frozenset[str]:
    """The paths of the files in `directory` that a process holds open, as
    `lsof` gives them, read once for each state, so each reader of a run
    sees one state, and one `lsof` call serves the runs of a session."""
    # lsof exits 1 where it finds no open file as well as on a fault, so
    # only its stderr tells a fault.
    out = subprocess.run(["lsof", "-F", "n", "+d", str(directory)],
                         capture_output=True, text=True)
    if out.stderr.strip():
        raise Refused(mctx("which files in {dir} a process holds open is unknown: "
                           "lsof says {err}").format(dir=directory,
                                                     err=out.stderr.strip()))
    return frozenset(line[1:] for line in out.stdout.splitlines() if line.startswith("n"))
