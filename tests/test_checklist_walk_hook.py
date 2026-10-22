"""The hook that holds an agent with a checklist to its walk: a handback
that passes with items unprinted ends a review on items the reviewer never
received, and nothing in the run shows it."""

import json

import pytest
from pathlib import Path

from engine import checkout
from handbook.checklist import Checklist
from handbook.paths import scripts_importable
from tests.hookrun import run_hook
from tests.codex_run import turn

scripts_importable()

AGENT = "a0000000000000001"
HOOK = checkout.scripts() / "checklist_walk_hook.py"
STEP = "uv run python scripts/step.py code-reviewer"


def session(tmp_path: Path, results: list[str], stops: dict[int, str] | None = None,
            messages: tuple[str, ...] = (), kind: str = "code-reviewer") -> str:
    """A session whose code reviewer `AGENT` made one step call for each
    of `results`, a stop at the item `stops` gives for its index, then
    received `messages`, and the hook input of its SubagentHandback call."""
    stops = stops or {}
    agents = tmp_path / "s" / "subagents"
    agents.mkdir(parents=True)
    (agents / f"agent-{AGENT}.meta.json").write_text(json.dumps({"agentType": kind}))
    lines: list[dict] = ([] if kind != "codex-launcher" else [
        {"type": "user", "message": {"content":
            "Codex mode: role `code-reviewer`, model `gpt-6.1-sol`, reasoning effort `medium`."}}])
    for n, result in enumerate(results):
        lines += [{"type": "assistant", "message": {"content": [
                      {"type": "tool_use", "id": f"t{n}", "name": "Bash",
                       "input": {"command": f"{STEP} --stop {stops[n]}" if n in stops
                                 else STEP}}]}},
                  {"type": "user", "toolUseResult": {"stdout": result}, "message": {"content": [
                      {"type": "tool_result", "tool_use_id": f"t{n}", "content": result}]}}]
    if kind == "codex-launcher":
        lines = [lines[0], turn(tmp_path / "codex", [
            (f"{STEP} --stop {stops[n]}" if n in stops else STEP, result)
            for n, result in enumerate(results)])]
    lines += [{"type": "user", "message": {"role": "user", "content": m}} for m in messages]
    (agents / f"agent-{AGENT}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
    (tmp_path / "s.jsonl").write_text("")
    return json.dumps({"tool_name": "SubagentHandback", "agent_id": AGENT,
                       "transcript_path": str(tmp_path / "s.jsonl"), "tool_input": {}})


def whole_walk() -> list[str]:
    c = Checklist("code-reviewer")
    out = [c.first()]
    for item in c.items:
        if item is not c.items[-1]:
            out.append(c.after(item.heading.text))
    return out


def denied(stdin: str) -> bool:
    code, out, err = run_hook(HOOK, stdin)
    assert code == 0 and "failed" not in err, err
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_a_whole_walk_is_allowed(tmp_path: Path) -> None:
    assert not denied(session(tmp_path, whole_walk()))


def test_a_walk_printed_whole_by_one_result_is_allowed(tmp_path: Path) -> None:
    assert not denied(session(tmp_path, ["\n".join(whole_walk())]))


def test_a_walk_cut_short_is_denied_once(tmp_path: Path) -> None:
    stdin = session(tmp_path, whole_walk()[:3])
    assert denied(stdin)
    assert not denied(stdin)


def test_a_later_round_that_stops_early_is_denied(tmp_path: Path) -> None:
    walk = whole_walk()
    assert denied(session(tmp_path, [*walk, walk[2]]))


def stopped(walk: list[str], at: int) -> tuple[list[str], dict[int, str]]:
    """The results of `walk` up to its item `at`, then a stop at that item."""
    c = Checklist("code-reviewer")
    item = c.items[at].heading.text
    return [*walk[:at + 1], c.stop(item)], {at + 1: f"'{item}'"}


def test_a_stop_at_an_item_the_walk_holds_is_allowed(tmp_path: Path) -> None:
    assert not denied(session(tmp_path, *stopped(whole_walk(), 2)))


def test_a_stop_past_the_walk_is_denied(tmp_path: Path) -> None:
    results, stops = stopped(whole_walk(), 2)
    del results[2]
    assert denied(session(tmp_path, results, {2: stops[3]}))


def test_a_step_call_after_a_stop_holds_the_whole_walk(tmp_path: Path) -> None:
    walk = whole_walk()
    results, stops = stopped(walk, 2)
    assert denied(session(tmp_path, [*results, walk[3]], stops))


def test_a_message_after_a_stop_holds_the_whole_walk(tmp_path: Path) -> None:
    results, stops = stopped(whole_walk(), 2)
    assert denied(session(tmp_path, results, stops, ("Do the item now.",)))


def test_a_launcher_is_held_to_its_roles_walk(tmp_path: Path) -> None:
    assert denied(session(tmp_path, whole_walk()[:3], kind="codex-launcher"))


def test_a_launcher_with_a_whole_walk_is_allowed(tmp_path: Path) -> None:
    assert not denied(session(tmp_path, whole_walk(), kind="codex-launcher"))


def test_a_launcher_with_no_codex_evidence_is_always_denied(tmp_path: Path) -> None:
    stdin = session(tmp_path, whole_walk(), kind="codex-launcher")
    (tmp_path / "codex" / "codex-events.jsonl").unlink()
    assert denied(stdin)
    assert denied(stdin)


def test_a_launcher_with_a_partial_walk_is_denied_once(tmp_path: Path) -> None:
    stdin = session(tmp_path, whole_walk()[:3], kind="codex-launcher")
    assert denied(stdin)
    assert not denied(stdin)


def test_a_codex_stop_is_bounded_until_a_message(tmp_path: Path) -> None:
    assert not denied(session(tmp_path, *stopped(whole_walk(), 2), kind="codex-launcher"))


def test_a_message_after_a_codex_stop_requires_the_rest(tmp_path: Path) -> None:
    assert denied(session(tmp_path, *stopped(whole_walk(), 2),
                          messages=("Continue.",), kind="codex-launcher"))


def test_a_launcher_cannot_substitute_its_own_walk(tmp_path: Path) -> None:
    stdin = session(tmp_path, whole_walk(), kind="codex-launcher")
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n")
    assert denied(stdin)


def test_malformed_codex_evidence_is_always_denied(tmp_path: Path) -> None:
    stdin = session(tmp_path, whole_walk(), kind="codex-launcher")
    (tmp_path / "codex" / "codex-events.jsonl").write_text("null\n")
    assert denied(stdin)
    assert denied(stdin)


def test_a_codex_walk_can_continue_across_a_resume(tmp_path: Path) -> None:
    results = whole_walk()
    stdin = session(tmp_path, results[:3], kind="codex-launcher")
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps({"type": "user", "message": {"content": "Here is the result."}}) + "\n")
        f.write(json.dumps(turn(tmp_path / "codex", [(STEP, r) for r in results[3:]], first=False)) + "\n")
    assert not denied(stdin)


def test_a_resume_input_removes_a_codex_stops_bound(tmp_path: Path) -> None:
    stdin = session(tmp_path, *stopped(whole_walk(), 2), kind="codex-launcher")
    assert not denied(stdin)
    path = tmp_path / "s" / "subagents" / f"agent-{AGENT}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps(turn(tmp_path / "codex", [], first=False,
                               text="The requested result is ready. Continue your walk.")) + "\n")
    assert denied(stdin)
    assert denied(stdin)


@pytest.mark.parametrize('writer', [
    "python -c \"print('uv run python scripts/step.py code-reviewer report')\"",
    "cat <<'REPORT'\nuv run python scripts/step.py code-reviewer report\nREPORT",
])
def test_report_writer_after_a_real_stop_preserves_the_bound(tmp_path, writer):
    stdin = session(tmp_path, *stopped(whole_walk(), 2))
    path = tmp_path / 's' / 'subagents' / f'agent-{AGENT}.jsonl'
    with path.open('a') as out:
        out.write(json.dumps({'type': 'assistant', 'message': {'content': [{
            'type': 'tool_use', 'name': 'Bash', 'id': 'writer',
            'input': {'command': writer}}]}}) + '\n')
        out.write(json.dumps({'type': 'user', 'message': {'content': [{
            'type': 'tool_result', 'tool_use_id': 'writer', 'content': ''}]}}) + '\n')
    assert not denied(stdin)


@pytest.mark.parametrize("command", [
    STEP + " | head -3", STEP + "; echo done", STEP + "; " + STEP,
    "/bin/zsh -lc '" + STEP + "; echo done'",
    STEP + " --stop report; echo done",
    "/bin/zsh -lc '" + STEP + "; " + STEP + "'",
])
def test_joined_work_does_not_count_as_a_step(command):
    from tests.conftest import script

    _calls = script("checklist_walk_hook")._calls

    entries = [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "step", "name": "Bash",
             "input": {"command": command}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "step", "content": "result"}]}},
    ]
    assert _calls(entries, "code-reviewer") == []
