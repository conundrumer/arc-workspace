"""The final replies of agents no record covers: the agents the coordinator
launched, which the stall reading reads."""

from final_replies import final_reply
from transcripts import find
from transcript_snapshots import SUBJECT_FAULTS

from controlled_markdown import mctx

from operations.state import Report


def reply_since(agent: str, since: float, undecided: list[str]) -> Report | None:
    """The final reply in the transcript of `agent`, where it gives one
    after `since`, or None where that transcript cannot be read."""
    try:
        r = final_reply(find(agent))
    except SUBJECT_FAULTS as exc:
        undecided.append(mctx("{run}: its transcript cannot be read ({error}), "
                              "so its final reply is not read").format(run=agent, error=exc))
        return None
    return r if r is not None and r.time > since else None


def stalled_reports(coordinators: dict[str, float], stalls: list[str],
                    undecided: list[str]) -> dict[str, Report]:
    """The final reply in the transcript of each agent of `stalls`, the
    agents whose `stall` reading fired (`operations.monitor`), that the
    coordinator launched, by `coordinators`, their launch times, given after
    its launch. An agent of an operator has its reports in the record of its
    attempt (`operations.attempt_view`), so no stall report stands in their
    place."""
    out: dict[str, Report] = {}
    for agent in stalls:
        since = coordinators.get(agent)
        if since is None or agent in out:
            continue
        r = reply_since(agent, since, undecided)
        if r is not None:
            out[agent] = r
    return out
