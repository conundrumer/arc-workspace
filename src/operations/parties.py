"""The party an open ticket waits on where no operator's step is due on
it by an exit (`Party`), as the selector of that exit's step names it,
and whether that party stands at a read of the state (`stands`), by its
kind alone."""

from dataclasses import dataclass
from enum import Enum

from controlled_markdown import mctx
from operations.directives import own_scope, paused
from operations.final_reply import live_holder
from operations.start_holds import hold
from operations.state import Agent, State
from operations.tracker import closed
from ticketing.exits import Exit


class Hold(Enum):
    """The holds of an open ticket: the start hold (`start_holds.hold`)
    and the lines of the user."""
    TAKES = mctx("the run scripts' `takes`")
    PAUSE = mctx("the `Op pause.` line")
    OWN_SCOPE = mctx("the `Op scope: own.` line")
    PACE = mctx("the usage pace")


@dataclass(frozen=True)
class Agents:
    """The agents `agents` of the operators', as the read gives them."""
    agents: tuple[Agent, ...]


@dataclass(frozen=True)
class Holder:
    """The holder `holder` of a ticket."""
    holder: str


@dataclass(frozen=True)
class OnTicket:
    """The ticket `number`."""
    number: str


@dataclass(frozen=True)
class ByExit:
    """The party of the exit `exit`, which no operator's step makes."""
    exit: Exit


type Party = Agents | Holder | OnTicket | Hold | ByExit


def stands(state: State, p: Party) -> bool:
    """Whether `p` stands at the read that gave `state`: agents where one
    of them is pending or the usage limit stopped it
    (`TranscriptsRead.limited`); a holder that is live
    (`final_reply.live_holder`) or that the usage limit stopped; a ticket that
    is not closed; the start hold where something holds agent starts; the
    `Op pause.` and the `Op scope: own.` line where it stands; the run
    scripts' `takes` where a run script defines it; and the party of an
    exit no operator's step makes, always."""
    match p:
        case Agents(agents):
            return any(a.pending or (a.agent_id is not None
                                     and a.agent_id in state.transcripts.limited)
                       for a in agents)
        case Holder(holder):
            return live_holder(state, holder) or holder in state.transcripts.limited
        case OnTicket(number):
            return not closed(state, number)
        case Hold.PACE:
            return hold(state) is not None
        case Hold.PAUSE:
            return paused(state)
        case Hold.OWN_SCOPE:
            return own_scope(state)
        case Hold.TAKES:
            return state.computed.admitted() is not None
        case ByExit():
            return True
