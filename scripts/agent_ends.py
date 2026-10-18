"""The ends of agents: the final replies their transcripts give, to the
operator that launched them or in a report file, and the agents read as
ended with them."""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from final_replies import final_reply
from filed_texts import filed_report, report_file, report_text
from open_agents import work_open
from transcripts import find, launched_find

from operations.state import Agent, Report


def reply_since(agent: str, since: float) -> Report | None:
    """The final reply in the transcript of `agent`, where it gives one
    after `since`."""
    r = final_reply(find(agent))
    return r if r is not None and r.time > since else None


def reply_to(a: Agent, since: float, undecided: list[str]) -> Report | None:
    """The final reply in the transcript of `a` after `since`, where its
    operator launched or last resumed it itself, so that reply went to
    that operator, or where it is the path of a report file alone
    (`filed_texts.report_file`), whichever agent it went to, read from
    that file, or None. A reply whose file is gone keeps the path as its
    text."""
    r = reply_since(a.agent_id, since) if a.agent_id else None
    path = report_file(r.text) if r is not None else None
    if r is None or path is None:
        return r if a.notifies else None
    text = report_text(path, a.agent_id or "", undecided)
    return r if text is None else replace(r, text=text, file=path)


def stalled_reports(agents: list[Agent], coordinators: dict[str, float],
                    stalls: list[str]) -> dict[str, Report]:
    """The final reply in the transcript of each agent of `stalls`, the
    agents whose `stall` reading fired (`operations.monitor`), that is
    pending, or that the coordinator launched, by `coordinators`, their
    launch times, given after its launch."""
    out: dict[str, Report] = {}
    launched = {a.agent_id: a.launched for a in agents if a.pending and a.agent_id}
    for agent in stalls:
        since = launched[agent] if agent in launched else coordinators.get(agent)
        if since is None or agent in out:
            continue
        r = reply_since(agent, since)
        if r is not None:
            out[agent] = r
    return out


def ended_with(a: Agent, reply: Report | None) -> Agent:
    """`a` as no longer pending, with `reply` as its last report."""
    return replace(a, waits=None, reports=a.reports if reply is None else (*a.reports, reply))


def ended_by(agents: Sequence[Agent], ended: Mapping[str, Report | None]) -> list[Agent]:
    """`agents`, each pending one of `ended` ended with the report it gives
    (`ended_with`), read as `filed_report` gives."""
    return [filed_report(ended_with(a, ended[a.agent_id]))
            if a.pending and a.agent_id is not None and a.agent_id in ended else a
            for a in agents]


def ended_elsewhere(agents: list[Agent], me: str,
                    undecided: list[str]) -> dict[str, Report | None]:
    """For each pending agent of another operator whose work is no longer
    open, an agent whose report reaches no running operator, and whose
    transcript is written (`transcripts.launched_find`), the final
    reply in its transcript that `reply_to` gives after its launch, or
    None."""
    out: dict[str, Report | None] = {}
    for a in agents:
        if not a.pending or a.operator == me or a.agent_id is None or a.agent_id in out:
            continue
        path = launched_find(a.agent_id)
        if path is None or work_open(path, []):
            continue
        out[a.agent_id] = reply_to(a, a.launched, undecided)
    return out
