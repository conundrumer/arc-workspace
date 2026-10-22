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
    from operations.state import Agent as Launched, Ended, Report, Tool
    from operations.steps import Send
    from operations.triage import for_coordinator
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"

    def analyst(*parts: tuple[float, str]) -> Launched:
        return Launched("a8e99dabca9ddb4de", ME, Role.TICKET_ANALYST,
                        analyst_subject(Purpose.DRAFT, "9-1"), "", 10.0, 10.0, Ended(),
                        tuple(Report(r, "Done.\n\n## For the coordinator\n" + p + "\n")
                              for r, p in parts), True)

    sent = "- decision: keep a\n- decision: drop b"
    first = for_coordinator(state(tmp_path, [t], [analyst((100.0, sent))], w))
    assert isinstance(first, Send)
    done = Entry("k", "k", "d", "o", ME, 150.0, Tool.SEND_MESSAGE, COORDINATOR, first.message,
                 None, None, Close(Outcome.DONE, 151.0, ""))
    s = state(tmp_path, [t], [analyst((100.0, sent), (200.0, later))], w)
    step = for_coordinator(replace(s, journal=Journal((done,))))
    assert isinstance(step, Send) is sends


def test_decision_sent_with_other_appended_text_goes_no_second_time(tmp_path: Path) -> None:
    from dataclasses import replace
    from operations.constants import COORDINATOR
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Ended, Report, Tool
    from operations.steps import labeled
    from operations.triage import for_coordinator
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "draft", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    items = "- decision: keep a\n- decision: drop b"
    a = Launched("a8e99dabca9ddb4de", ME, Role.TICKET_ANALYST,
                 analyst_subject(Purpose.DRAFT, "9-1"), "", 10.0, 10.0, Ended(),
                 (Report(100.0, "Done.\n\n## For the coordinator\n" + items + "\n"),), True)
    key = "ticket analyst a8e99dabca9ddb4de, reply at 100"
    done = Entry("k", "k", "d", "o", ME, 150.0, Tool.SEND_MESSAGE, COORDINATOR,
                 labeled(key, items + "\n\nRule it by the line `Decision: abc <choice>`."),
                 None, None, Close(Outcome.DONE, 151.0, ""))
    s = state(tmp_path, [t], [a], w)
    assert for_coordinator(replace(s, journal=Journal((done,)))) is None


def test_a_retired_relay_gives_way_to_the_next_analysts(tmp_path: Path) -> None:
    from dataclasses import replace
    from operations.journal import Close, Entry, Journal, Outcome
    from operations.order import placed
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Ended, Report, Tool
    from operations.steps import Send, key
    from operations.triage import for_coordinator
    from tests.test_unreported_agents import ME, state, ticket as filed
    log = "\n## Log\n2026-10-17T02:14:06Z draft [ticket-analyst]: filed\n"
    tickets = [filed(tmp_path, "draft", f"9-{n}_change_x_ticket-analyst.md",
                     "---\nkind: change\neditors: code-editor\n---\n# x: y\n" + log)
               for n in (1, 2)]
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"

    def analyst(agent_id: str, n: int, at: float) -> Launched:
        return Launched(agent_id, ME, Role.TICKET_ANALYST, analyst_subject(Purpose.DRAFT, f"9-{n}"),
                        "", 10.0, 10.0, Ended(),
                        (Report(at, f"Done.\n\n## For the coordinator\n- decision: keep {n}\n"),),
                        True)

    s = state(tmp_path, tickets, [analyst("a0000000000000001", 1, 100.0),
                                  analyst("a0000000000000002", 2, 200.0)], w)
    first = for_coordinator(s)
    assert isinstance(first, Send) and "keep 1" in first.message
    retiring = Entry("r", "r", "d", "o", ME, 150.0, Tool.BASH, None, "file the bug",
                     key(first), None, Close(Outcome.DONE, 151.0, ""))
    step, _ = placed(replace(s, journal=Journal((retiring,))), for_coordinator)
    assert isinstance(step, Send) and "keep 2" in step.message


def test_an_analyst_whose_tickets_all_stand_closed_gets_no_relay(tmp_path: Path) -> None:
    from operations.roles import Purpose, Role, analyst_subject
    from operations.state import Agent as Launched, Ended, Report
    from operations.triage import for_coordinator
    from tests.test_unreported_agents import ME, state, ticket as filed
    t = filed(tmp_path, "closed", "9-1_change_x_ticket-analyst.md",
              "---\nkind: change\neditors: code-editor\n---\n# x: y\n\n## Log\n"
              "2026-10-17T02:14:06Z closed [ticket-analyst]: wontfix: x\n")
    w = tmp_path / "main" / ".claude" / "worktrees" / "w"
    a = Launched("a0000000000000001", ME, Role.TICKET_ANALYST, analyst_subject(Purpose.DRAFT, "9-1"),
                 "", 10.0, 10.0, Ended(),
                 (Report(100.0, "Done.\n\n## For the coordinator\n- decision: keep 1\n"),), True)
    assert for_coordinator(state(tmp_path, [t], [a], w)) is None
