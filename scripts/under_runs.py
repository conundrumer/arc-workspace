"""The runs `--under` of `profile_runs.py` takes under a run: those since
an operator's previous call of it on that run, as `profile_runs.py --help`
gives them."""

from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx

from agent_launches import runs_under
from agent_turns import first_time, last_time
from command_labels import programs
from context_bound_hook import OPERATOR
from open_agents import work_open
from run_reads import BACKGROUND_TASK, agent_type, blocks, result_text
from ticketing.times import utc_stamp
from transcripts import agent_id, agent_transcripts, bare_id
from transcript_entries import Entry, epoch, read_entries

from operations.batches import LEFT_OPEN, NO_RUN, RUNS_TAKEN, lines, read_under

PROFILE_SCRIPT = "profile_runs.py"
"""The script whose `UNDER` calls an operator's previous call is read from."""

UNDER = "--under"
"""The option of the mode that profiles the runs under a run since an
operator's previous call of it."""

def calls_under(command: str, ident: str) -> bool:
    """Whether the Bash command `command` runs `PROFILE_SCRIPT` with `UNDER`
    on the run `ident`, as it writes the ID, with or without the `agent-`
    prefix."""
    want = bare_id(ident)
    for prog, rest in programs(command):
        if prog != PROFILE_SCRIPT:
            continue
        for i, word in enumerate(rest):
            given = (rest[i + 1] if word == UNDER and i + 1 < len(rest)
                     else word.removeprefix(UNDER + "=")
                     if word.startswith(UNDER + "=") else None)
            if given is not None and bare_id(given) == want:
                return True
    return False


def under_output(entries: list[Entry], call: str) -> str | None:
    """The text of the result of the Bash call `call` among `entries`,
    where that result says it completed in the foreground with no error, or
    None otherwise."""
    for e in entries:
        for b in blocks(e, "tool_result"):
            if e.get("type") == "user" and b.get("tool_use_id") == call:
                r = e.get("toolUseResult")
                r = r if isinstance(r, dict) else {}
                if b.get("is_error") or r.get(BACKGROUND_TASK) or r.get("interrupted"):
                    return None
                return result_text(b, r)
    return None


@dataclass(frozen=True)
class Previous:
    """The previous call of `UNDER` on a run: its time, the agent id of the
    operator that made it, and the agent ids its `LEFT_OPEN` line gives."""
    time: float
    agent: str
    left: frozenset[str]


def previous_call(path: Path, ident: str, undecided: list[str]) -> Previous | None:
    """The previous call of `UNDER` on the run at `path`, which `ident`
    names, as `profile_runs_help.PARTS` gives that call, or None where
    none stands."""
    start = first_time(path)
    found: Previous | None = None
    for p in (p for ps in agent_transcripts().values() for p in ps):
        if start is not None and p.stat().st_mtime < start:
            continue
        if agent_type(p) != OPERATOR:
            continue
        calls = read_entries(p, naming={UNDER})
        made = {b["id"]: epoch(e["timestamp"]) for e in calls
                if e.get("type") == "assistant" and e.get("timestamp")
                for b in blocks(e, "tool_use")
                if b.get("name") == "Bash" and b.get("id")
                and calls_under(str((b.get("input") or {}).get("command", "")), ident)}
        if not made:
            continue
        results = read_entries(p, naming=set(made))
        for call, t in made.items():
            text = under_output(results, call)
            if text is None:
                continue
            if (n := len(lines(text, LEFT_OPEN))) > 1:
                undecided.append(mctx(
                    "the result of the call of `{under}` at {time} by {agent} "
                    "holds {n} `{left}` lines, so it counts as no call").format(
                        under=UNDER, time=utc_stamp(t),
                        agent=agent_id(p), n=n, left=LEFT_OPEN))
                continue
            given = read_under(text)
            if given is not None and (found is None or t > found.time):
                found = Previous(t, agent_id(p), given.left)
    return found


def runs_since(path: Path, ident: str, undecided: list[str]) -> list[Path]:
    """The runs `UNDER` takes under the run at `path`, which `ident` names,
    with its first lines printed."""
    previous = previous_call(path, ident, undecided)
    taken: list[Path] = []
    left: list[str] = []
    for p in runs_under(path):
        last = last_time(p)
        if not (previous is None or agent_id(p) in previous.left
                or (last is not None and last > previous.time)):
            continue
        if work_open(p, undecided):
            left.append(agent_id(p))
        else:
            taken.append(p)
    print(LEFT_OPEN, " ".join(left) or NO_RUN)
    print(RUNS_TAKEN, len(taken), *(agent_id(p) for p in taken))
    # The harness trims the end of a result's `stdout`, so the line after
    # `RUNS_TAKEN` gives it the line break `read_under` needs.
    if previous is None:
        print(mctx("previous call: none"))
    else:
        print(mctx("previous call: {time} by {agent}").format(
            time=utc_stamp(previous.time),
            agent=previous.agent))
    return taken
