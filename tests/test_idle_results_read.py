"""A state read gives an operator's calls of `next` that printed that
nothing is ready with their result text, so `plan.idle_since` finds the first
of them, and gives no `undecided` line for an Agent call whose result gives
the launched agent's id while no `.meta.json` gives it as a launch."""

import json
import sys
from pathlib import Path

from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
script("operator_transcript")
agent_launches = script("agent_launches")
operator_transcript = sys.modules["operator_transcript"]
transcripts = sys.modules["transcripts"]
from tests.test_agent_launches import add, at, call, result  # noqa: E402

OPERATOR = "a0000000000000005"


def next_use(tid: str, s: int) -> dict:
    from operations.command_words import next_command
    return {"type": "assistant", "timestamp": at(s), "message": {"content": [
        {"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": next_command(OPERATOR)}}]}}


def printed(tid: str, s: int, text: str) -> dict:
    return {"type": "user", "timestamp": at(s), "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": text}]}}


def test_idle_since_finds_the_first_of_the_calls_of_next_that_printed_nothing_ready(
        tmp_path: Path) -> None:
    from operations.plan import idle_since
    from operations.printed_forms import POLL_AGAIN
    path = tmp_path / f"agent-{OPERATOR}.jsonl"
    path.with_suffix(".meta.json").write_text(json.dumps({"agentType": "operator"}))
    add(path, {"type": "user", "timestamp": at(0), "message": {"content": "brief"}},
        next_use("n1", 1), printed("n1", 2, "call Agent"),
        next_use("n2", 3), printed("n2", 4, POLL_AGAIN),
        next_use("n3", 5), printed("n3", 6, POLL_AGAIN))
    transcripts.new_state()
    read = operator_transcript.read_operator(OPERATOR, path, tmp_path, [], {})
    assert idle_since(read.calls, OPERATOR) == operator_transcript.epoch(at(3))


def test_an_agent_call_whose_result_gives_the_agent_id_leaves_nothing_undecided(
        tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    add(path, {"type": "user", "timestamp": at(0), "message": {"content": "brief"}},
        call("t1", 1), result("t1", 2, "async_launched", "a1"))
    transcripts.new_state()
    undecided: list[str] = []
    assert [launch.agent for launch in agent_launches.launches(path, undecided)] == ["a1"]
    assert undecided == []
