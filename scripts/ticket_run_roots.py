"""Run ids recorded by a fixed ticket close."""

from operations.state import Ticket
from ticketing.vocabulary import Resolution, Status


def ticket_runs(t: Ticket) -> list[str]:
    """The run ids from the final fixed close, or none where there is none."""
    closing = [line for line in t.log if line.status is Status.CLOSED
               and line.resolution is Resolution.FIXED]
    return closing[-1].note.split()[3:] if closing else []

