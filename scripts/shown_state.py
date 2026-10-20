"""The state the ticket dashboard shows of a read of the operator's state
(`Shown`), and its record in the file `SHOWN` in the session's
scratchpad, a JSON object written by `write_shown` and read by
`shown_read`."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from session_records import replaced

from operations import change_take, start_holds, ticket_stall, triage, unwaited
from operations.directives import Directive, own_scope, pace, paused, session_lines
from operations.pacing import Capped, Pace, Scripted, Until
from operations.parties import Hold, OnTicket, Party
from operations.roles import Role
from operations.state import NotComputed, State
from operations.admission import in_scope
from operations.taking import expedited

SHOWN = "shown-state.json"
"""The name of the file, in the session's scratchpad, that holds the
`Shown` of the operator's last read of the state."""


@dataclass(frozen=True)
class ScriptAdmits:
    """The pace of an `Op pace: <path>` line, as `Shown` keeps it: whether
    the script admits a step that starts an agent's run."""
    admits: bool


type ShownPace = Until | ScriptAdmits | NotComputed

type ShownHold = ShownPace | Capped
"""What holds agent starts (`start_holds.hold`), as `Shown` keeps it."""

type ShownParty = Hold | OnTicket
"""The party a ticket the operators start next waits on, as `Shown` keeps
it."""


@dataclass(frozen=True)
class ShownAgent:
    """A pending agent of the session's operators: its role, the time of its
    launch and the tickets it is at work on (`ticket_stall.agents_by_ticket`)."""
    role: Role
    launched: float
    tickets: tuple[str, ...]


@dataclass(frozen=True)
class Start:
    """A ticket the operators start next, with the party that holds it, or
    None where none does."""
    number: str
    held: ShownParty | None


@dataclass(frozen=True)
class Shown:
    """The values of a read of the state that the ticket dashboard shows:
    the time of the read, the text of the `Op pace:` line in force, or None
    where the pace is the default, the pace computed, whether the session
    is paused and keeps to its own scope, the tickets its own scope admits
    (`admission.in_scope`) where it keeps to it and the record gives them,
    None otherwise, the tickets expedited, the
    pending agents, the tickets that wait on nothing with the time from
    which each has stood so (`unwaited.unwaited`), what holds agent starts
    where something does, and the tickets the operators start next, in the
    order the step logic takes them: those `triage.selection` selects, then
    those it holds, then the changes of `change_take.ready`, those of
    `change_take.takeable` first."""
    at: float
    pace_line: str | None
    pace: ShownPace
    paused: bool
    own_scope: bool
    in_scope: frozenset[str] | None
    expedited: tuple[str, ...]
    agents: tuple[ShownAgent, ...]
    unwaited: Mapping[str, float]
    start_hold: ShownHold | None
    starts: tuple[Start, ...]


def shown_pace(p: Pace) -> ShownPace:
    """`p` as `Shown` keeps it."""
    match p:
        case Scripted(_, admits):
            return ScriptAdmits(admits)
        case other:
            return other


def shown_party(p: Party) -> ShownParty:
    """`p`, which `triage.selection` or `change_take.left` gives. Raises
    ValueError on a party of another kind."""
    match p:
        case Hold() | OnTicket():
            return p
        case _:
            raise ValueError(f"no ticket the operators start next waits on {p!r}")


def starts(state: State) -> tuple[Start, ...]:
    """`Shown.starts` of `state`."""
    selected, held = triage.selection(state)
    ready = change_take.ready(state)
    first = change_take.takeable(state)
    firsts = {t.number for t in first}
    left = change_take.left(state)
    return (*(Start(n, None) for n in selected),
            *(Start(n, h) for n, h in held.items()),
            *(Start(t.number, None if (p := left.get(t.number)) is None else shown_party(p))
              for t in [*first, *(t for t in ready if t.number not in firsts)]))


def shown(state: State) -> Shown:
    """The `Shown` of `state`."""
    lines = [ln.text for ln in session_lines(state) if ln.kind is Directive.PACE]
    by_ticket = ticket_stall.agents_by_ticket(state)
    held = start_holds.hold(state)
    return Shown(state.now, lines[-1] if lines and pace(state) is not None else None,
                 shown_pace(state.computed.pace), paused(state), own_scope(state),
                 frozenset(in_scope(state)) if own_scope(state) else None,
                 tuple(sorted(expedited(state))),
                 tuple(ShownAgent(a.role, a.launched,
                                  tuple(n for n, xs in by_ticket.items() if any(x is a for x in xs)))
                       for a in state.transcripts.agents if a.pending),
                 dict(sorted(unwaited.unwaited(state).items())),
                 None if held is None else held if isinstance(held, Capped) else shown_pace(held),
                 starts(state))


def pace_json(p: ShownHold) -> dict[str, object]:
    """The JSON form of `p`, which `pace_of` reads."""
    match p:
        case Until(at, cap):
            return {"until": at, "cap": cap}
        case ScriptAdmits(admits):
            return {"script_admits": admits}
        case NotComputed(why):
            return {"not_computed": why}
        case Capped(cap):
            return {"capped": cap}


def pace_of(p: Any) -> ShownHold:
    """The value whose JSON form (`pace_json`) is `p`."""
    if "until" in p:
        return Until(float(p["until"]), None if p["cap"] is None else int(p["cap"]))
    if "script_admits" in p:
        return ScriptAdmits(bool(p["script_admits"]))
    if "capped" in p:
        return Capped(int(p["capped"]))
    return NotComputed(str(p["not_computed"]))


def party_json(p: ShownParty | None) -> dict[str, str] | None:
    """The JSON form of `p`, which `party_of` reads."""
    match p:
        case None:
            return None
        case Hold():
            return {"hold": p.name}
        case OnTicket(number):
            return {"on": number}


def party_of(p: Any) -> ShownParty | None:
    """The value whose JSON form (`party_json`) is `p`."""
    if p is None:
        return None
    return Hold[p["hold"]] if "hold" in p else OnTicket(str(p["on"]))


def write_shown(here: Path, state: State) -> None:
    """Replaces the file `SHOWN` under `here` with the `Shown` of `state`."""
    s = shown(state)
    replaced(here, SHOWN, {
        "at": s.at, "pace_line": s.pace_line, "pace": pace_json(s.pace), "paused": s.paused,
        "own_scope": s.own_scope,
        "in_scope": None if s.in_scope is None else sorted(s.in_scope), "expedited": list(s.expedited),
        "agents": [{"role": a.role.value, "launched": a.launched, "tickets": list(a.tickets)}
                   for a in s.agents],
        "unwaited": dict(s.unwaited),
        "start_hold": None if s.start_hold is None else pace_json(s.start_hold),
        "starts": [{"number": x.number, "held": party_json(x.held)} for x in s.starts]})


def shown_read(here: Path) -> Shown | str:
    """The `Shown` the file `SHOWN` under `here` holds, or why there is
    none: the file is missing, or does not hold the JSON `write_shown`
    writes. A record with no `in_scope` key, written before records gave
    it, gives `Shown.in_scope` as None."""
    try:
        r = json.loads((here / SHOWN).read_text())
    except OSError:
        return f"no read of the state is recorded ({here / SHOWN} is missing)"
    except ValueError as e:
        return f"the record {here / SHOWN} does not parse: {e}"
    try:
        kept = pace_of(r["pace"])
        if isinstance(kept, Capped):
            raise ValueError(f"the pace {kept!r} is a hold")
        return Shown(float(r["at"]), None if r["pace_line"] is None else str(r["pace_line"]), kept,
                     bool(r["paused"]), bool(r["own_scope"]),
                     None if (w := r.get("in_scope")) is None else frozenset(map(str, w)), tuple(map(str, r["expedited"])),
                     tuple(ShownAgent(Role(a["role"]), float(a["launched"]), tuple(map(str, a["tickets"])))
                           for a in r["agents"]),
                     {str(n): float(t) for n, t in r["unwaited"].items()},
                     None if r["start_hold"] is None else pace_of(r["start_hold"]),
                     tuple(Start(str(x["number"]), party_of(x["held"])) for x in r["starts"]))
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return f"the record {here / SHOWN} does not hold a read of the state: {e!r}"
