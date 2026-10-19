"""A ticket analyst's `decision:` items sent to the coordinator again from
a later reply, whose fault would go on with no sign."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(("later", "sends"), [("- decision: keep a\n- decision: drop b", False),
                                               ("- decision: drop b", True),
                                               ("- decision: keep a", True)])
def test_decision_goes_to_the_coordinator_once(tmp_path: Path, later: str, sends: bool) -> None:
    from dataclasses import replace
    from operations.constants import COORDINATOR
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Report, Tool
    from operations.steps import Send
    from operations.triage import for_coordinator
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"

    def analyst(*parts: tuple[float, str]) -> Launched:
        return Launched("a8e99dabca9ddb4de", ME, Role.TICKET_ANALYST,
                        analyst_subject(Purpose.DRAFT, "9-1"), "", 10.0, 10.0, None,
                        tuple(Report(r, "Done.\n\n## For the coordinator\n" + p + "\n")
                              for r, p in parts), True)

    sent = "- decision: keep a\n- decision: drop b"
    first = for_coordinator(state(tmp_path, [t], [analyst((100.0, sent))], w))
    assert isinstance(first, Send)
    done = Entry("k", "d", "o", ME, 150.0, Tool.SEND_MESSAGE, COORDINATOR, first.message,
                 None, None, Close(Outcome.DONE, 151.0, ""))
    s = state(tmp_path, [t], [analyst((100.0, sent), (200.0, later))], w)
    step = for_coordinator(replace(s, journal=Journal((done,))))
    assert isinstance(step, Send) is sends
