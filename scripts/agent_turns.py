"""The turns of an agent's run, read from its transcripts, as
`profile_runs.py --help runs` gives them."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path

from controlled_markdown import mctx
from run_reads import blocks, is_prompt, text_of
from senders import is_interrupt_note
from state_reads import DERIVED, Kept, state_cache
from transcripts import agent_id, chain
from entry_reads import entries_back, entries_forward, read_entries
from transcript_entries import epoch
from transcript_snapshots import Entry

# The types of a transcript's message entries, the entries of a turn: the
# message that opens it and its work.
MESSAGE_TYPES = ("user", "assistant")

# The starts of the text of the entries the harness writes for a local
# command, such as /compact, and for its output.
LOCAL_COMMAND = ("<command-name>", "<local-command-")


def turns(entries: Sequence[Entry]) -> tuple[set[int], set[int]]:
    """The indices of the entries that start a turn and of those that end
    one. A prompt starts a turn when the next message entry is the model's,
    or when no message entry follows it and it gives the model a message
    it has not answered yet; a local command, such as /compact, and the
    harness's note that the user interrupted the run give it none. An assistant
    entry with no tool call ends a turn when it says so, or when the next
    message entry is a prompt, and the result of a call that ends the turn,
    such as SubagentHandback, ends one. The harness's note that the user
    interrupted the run ends one unless the next message entry is the
    model's."""
    starts: set[int] = set()
    ends: set[int] = set()
    for i, (_, start, end) in zip(range(len(entries) - 1, -1, -1), turn_marks(reversed(entries))):
        if start:
            starts.add(i)
        if end:
            ends.add(i)
    return starts, ends


def turn_marks(back: Iterable[Entry]) -> Iterator[tuple[Entry, bool, bool]]:
    """Each entry of `back`, a run's entries last first, with whether it
    starts a turn and whether it ends one, as `turns` gives them: each
    mark rests only on the entries after it, so a reader that stops early
    parses none of the entries before."""
    nxt: Entry | None = None
    for e in back:
        yield e, *marks(e, nxt)
        if is_message(e):
            nxt = e


def marks(entry: Entry, nxt: Entry | None) -> tuple[bool, bool]:
    """Whether `entry` starts a turn and whether it ends one, as `turns`
    gives them, where `nxt` is the next message entry after it
    (`is_message`), or None where none follows."""
    start = is_prompt(entry) and (nxt is not None and nxt.get("type") == "assistant"
                                  or nxt is None and gives_model(entry))
    end = False
    if entry.get("type") == "assistant" and not blocks(entry, "tool_use"):
        stop = (entry.get("message") or {}).get("stop_reason")
        end = stop in ("end_turn", "stop_sequence") or (nxt is not None and is_prompt(nxt))
    if entry.get("toolEndsTurn"):
        end = True
    if is_interrupt_note(entry) and (nxt is None or nxt.get("type") != "assistant"):
        end = True
    return start, end


def gives_model(entry: Entry) -> bool:
    """Whether a prompt gives the model a message: it is neither a local
    command nor the harness's note that the user interrupted the run."""
    if is_interrupt_note(entry):
        return False
    return entry.get("type") != "user" or not text_of(
        (entry.get("message") or {}).get("content")).lstrip().startswith(LOCAL_COMMAND)


def is_message(entry: Entry) -> bool:
    """Whether `entry` is a message entry, whose type `turns` reads at the
    entries before it: an entry of a turn or a prompt."""
    return is_turn_entry(entry) or is_prompt(entry)


def run_back(path: Path) -> Iterator[Entry]:
    """The entries of the run at `path`, across its transcripts, last
    first, each line parsed only when it is reached."""
    return (e for p in reversed(chain(path)) for e in entries_back(p))


def idle_after(idle: bool, i: int, entry: Entry, starts: set[int],
               ends: set[int]) -> bool:
    """Whether a run is idle after its `i`-th entry, from `idle`, whether it
    was before it."""
    if i in ends:
        return True
    return idle and entry.get("type") != "assistant" and i not in starts


def turn_ended(entries: Sequence[Entry]) -> bool:
    """Whether the run whose entries are `entries`, or those from one of its
    timestamped assistant entries on, has ended its turn, as
    `profile_runs.py --help runs` gives when a turn ended. An entry with no timestamp moves
    no turn."""
    starts, ends = turns(entries)
    idle = False
    for i, e in enumerate(entries):
        if e.get("timestamp"):
            idle = idle_after(idle, i, e, starts, ends)
    return idle


@state_cache(DERIVED, kept=Kept.DISK)
def turn_end(path: Path) -> float | None:
    """The time of the last timestamped entry of the run at `path` that
    ends a turn (`turns`), as `profile_runs.py --help runs` gives when a
    turn ended, with only the lines from it to the end parsed."""
    return next((epoch(e["timestamp"]) for e, _, end in turn_marks(run_back(path))
                 if end and e.get("timestamp")), None)


@state_cache(DERIVED, kept=Kept.DISK)
def has_ended(path: Path) -> bool:
    """`turn_ended` over the run at `path`, read from its last entry back to
    its last timestamped assistant entry, which settles it."""
    tail: list[Entry] = []
    for e in run_back(path):
        tail.append(e)
        if e.get("type") == "assistant" and e.get("timestamp"):
            break
    return turn_ended(tail[::-1])


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def turn_after(path: Path, t: float, undecided: list[str]) -> bool:
    """Whether the transcript at `path` holds an entry of a turn timestamped
    after `t`. An entry of a turn with no timestamp counts as not, and an
    `undecided` line names the run."""
    out = False
    for e in read_entries(path):
        if not is_turn_entry(e):
            continue
        if not e.get("timestamp"):
            undecided.append(mctx("{run}: a `{type}` entry of its transcript has no "
                                  "timestamp, so it counts as before the latest sign, "
                                  "outside its transcript, that its turn ended").format(
                run=agent_id(path), type=e.get("type")))
        elif epoch(e["timestamp"]) > t:
            out = True
    return out


@state_cache(DERIVED)
def last_time(path: Path, holds: Callable[[Entry], bool] | None = None) -> float | None:
    """The time of the last timestamped entry of the run at `path`, of the
    entries `holds` gives where it is given, held while the reads of the
    run's transcripts it made stand."""
    return next((epoch(e["timestamp"]) for e in run_back(path)
                 if e.get("timestamp") and (holds is None or holds(e))), None)


@state_cache(DERIVED, kept=Kept.DISK)
def latest_time(path: Path) -> float | None:
    """The time of the last timestamped entry of the run at `path`, with
    only the lines from it to the end parsed."""
    return last_time(path)


@state_cache(DERIVED, kept=Kept.DISK)
def first_time(path: Path) -> float | None:
    """The time of the first timestamped entry of the run at `path`, with
    only the lines up to it parsed."""
    for p in chain(path):
        for e in entries_forward(p):
            if e.get("timestamp"):
                return epoch(e["timestamp"])
    return None


def is_turn_entry(entry: Entry) -> bool:
    return entry.get("type") in MESSAGE_TYPES
