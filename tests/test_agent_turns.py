"""Whether a run's turn has ended, which `open_agents.work_open` and the
end of a run read: a misread entry gives a run at work as ended, or one
that ended as at work, without any failure."""

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
agent_turns = script("agent_turns")


def handback(t: str, tid: str) -> list[dict]:
    return [{"type": "assistant", "timestamp": t,
             "message": {"content": [{"type": "tool_use", "id": tid,
                                      "name": "SubagentHandback", "input": {}}],
                         "stop_reason": "tool_use"}},
            {"type": "user", "timestamp": t, "toolEndsTurn": True,
             "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                      "content": "ok"}]}}]


def attachment(t: str) -> dict:
    return {"type": "attachment", "timestamp": t, "attachment": {"type": "skill_listing"}}


def user(t: str, text: str) -> dict:
    return {"type": "user", "timestamp": t, "message": {"content": text}}


def test_unanswered_message() -> None:
    cut = [*handback("2026-10-18T09:44:56.649Z", "t1"),
           attachment("2026-10-18T09:44:57.058Z"),
           user("2026-10-18T09:50:29.228Z",
                "Another Claude session sent a message while you were working: "
                '<agent-message from="aaf59d595bac57758">'),
           attachment("2026-10-18T09:50:29.329Z"),
           attachment("2026-10-18T09:50:29.494Z")]
    assert not agent_turns.turn_ended(cut)
    assert agent_turns.turn_ended([*cut, *handback("2026-10-18T09:50:55.000Z", "t2")])


def test_local_command() -> None:
    entries = [*handback("2026-10-18T09:44:56.649Z", "t1"),
               user("2026-10-18T09:45:00.000Z", "<command-name>/compact</command-name>")]
    assert agent_turns.turn_ended(entries)
