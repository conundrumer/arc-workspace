"""The dashboard words for local times and scheduling holds."""

import time

from shown_state import ScriptAdmits, ShownParty
from operations.pacing import Capped, Until
from operations.parties import Hold, OnTicket
from operations.state import NotComputed


def clock(at: float, now: float) -> str:
    """The local time `at`, with its day where it is not the day of `now`."""
    same = time.localtime(at)[:3] == time.localtime(now)[:3]
    return time.strftime("%-I:%M %p" if same else "%a %-I:%M %p", time.localtime(at))


def hold_text(h: ShownParty) -> str:
    match h:
        case Hold.PAUSE:
            return "Held by your pause"
        case Hold.OWN_SCOPE:
            return "Held by your own-scope line"
        case Hold.PACE:
            return "Held by the Claude usage pace"
        case Hold.TAKES:
            return "Held by the run scripts' takes"
        case OnTicket(number):
            return f"Starts after {number}"


def start_hold_text(h: ScriptAdmits | Until | NotComputed | Capped, now: float) -> str:
    match h:
        case Until(at, _):
            return f"The Claude pace holds Claude starts until {clock(at, now)}"
        case Capped(cap):
            return f"The Claude pace's cap of {cap} running workers holds Claude starts"
        case ScriptAdmits():
            return "The Claude pace script holds Claude starts"
        case NotComputed(why):
            return f"Claude starts are held: the pace is not computed ({why})"

