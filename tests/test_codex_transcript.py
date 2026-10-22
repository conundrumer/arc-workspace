"""Review coverage must not silently include other turns or omit inner results."""

import json

from tests.conftest import script
from tests.test_codex_spends import at, launch, record

reader = script("codex_transcript")
spends = script("spends")
measure = script("codex_spends")


def fixture(tmp_path, monkeypatch, records, payloads, entries=None):
    launcher = tmp_path / "launcher.jsonl"
    launcher.write_text("")
    monkeypatch.setattr(measure, "run_entries", lambda _: iter(entries or [launch(tmp_path)]))
    (tmp_path / "codex-events.jsonl").write_text(
        ''.join(json.dumps(r) + '\n' for r in records))
    directory = tmp_path / ".codex" / "sessions"
    directory.mkdir(parents=True)
    path = directory / "rollout-now-thread.jsonl"
    path.write_text(''.join(json.dumps({"timestamp": at(11 + i), **p}) + '\n'
                            for i, p in enumerate(payloads)))
    return launcher, path


def event(kind, **values):
    return {"type": "event_msg", "payload": {"type": kind, **values}}


def response(kind, **values):
    return {"type": "response_item", "payload": {"type": kind, **values}}


def test_accepted_failed_and_resumed_turns_exclude_later_work(tmp_path, monkeypatch):
    launcher, _ = fixture(tmp_path, monkeypatch,
        [record(turn="a"), record(turn="b", start=21)], [
            event("task_started", turn_id="a"),
            response("function_call", name="read_file", call_id="inner", arguments='{}'),
            response("function_call_output", call_id="inner", output="inner tool result"),
            event("turn_aborted", turn_id="a"),
            event("task_started", turn_id="b"),
            event("item_completed", item={"type": "CommandExecution", "command": "pwd",
                                           "aggregated_output": "exec result"}),
            event("task_complete", turn_id="b"),
            event("task_started", turn_id="later"),
            response("message", role="assistant", content=[{"text": "unrelated"}]),
            event("task_complete", turn_id="later")],
        entries=[launch(tmp_path), launch(tmp_path, 20, call="resume")])
    result = reader.read(launcher, tmp_path)
    assert [t.turn for _, _, t in result.turns] == ["a", "b"]
    text = json.dumps([reader.activity(t) for _, _, t in result.turns])
    assert "inner tool result" in text and "exec result" in text
    assert "unrelated" not in text
    assert result.turns[0][2].end_state == "turn_aborted"
    assert {s.role for s, _, _ in result.turns} == {"code-editor"}


def test_partial_tail_and_missing_rollout_remain_gaps(tmp_path, monkeypatch):
    launcher, path = fixture(tmp_path, monkeypatch, [record()], [
        event("task_started", turn_id="turn"), response("message", role="assistant",
                                                                  content=[{"text": "visible"}])])
    with path.open('a') as out:
        out.write('{"type": "event_msg"')
    result = reader.read(launcher, tmp_path)
    assert result.coverage is reader.Coverage.GAP
    assert result.turns[0][2].ended is None
    path.unlink()
    result = reader.read(launcher, tmp_path)
    assert result.gaps and not result.turns


def test_projection_duplicates_and_pagination(tmp_path, monkeypatch, capsys):
    launcher, _ = fixture(tmp_path, monkeypatch, [record()], [
        event("task_started", turn_id="turn"),
        response("message", role="assistant", content=[{"text": "visible message"}]),
        event("agent_message", message="visible message"),
        response("function_call", name="exec_command", call_id="inner", arguments='{}'),
        event("exec_command_begin", call_id="inner", command=["pwd"]),
        response("function_call_output", call_id="inner", output="inner result"),
        event("exec_command_end", call_id="inner", command=["pwd"], output="inner result"),
        event("task_complete", turn_id="turn")])
    result = reader.read(launcher, tmp_path)
    text = json.dumps(reader.activity(result.turns[0][2]))
    assert text.count("visible message") == 1 and text.count("inner result") == 1
    monkeypatch.setattr(reader, "find", lambda _: launcher)
    monkeypatch.setattr(reader, "read", lambda _: result)
    assert reader.main(["launcher", "--limit", "2"]) == 0
    assert "--offset 2 --limit 2" in capsys.readouterr().out
    assert reader.main(["launcher", "--offset", "2"]) == 0
    assert "inner result" in capsys.readouterr().out


def test_unmatched_record_is_gap_and_no_calls_is_distinct(tmp_path, monkeypatch):
    launcher, _ = fixture(tmp_path, monkeypatch, [record(), record(turn="extra")], [])
    assert reader.read(launcher, tmp_path).coverage is reader.Coverage.GAP
    monkeypatch.setattr(measure, "run_entries", lambda _: iter([]))
    assert reader.read(launcher, tmp_path).coverage is reader.Coverage.NONE


def test_bad_launcher_entry_does_not_hide_accepted_work(tmp_path, monkeypatch):
    bad = launch(tmp_path, call="bad")
    bad["message"]["content"][0]["input"]["command"] = (
        "uv run python scripts/codex_agent.py code-editor $SCRATCH brief gpt-6.1-sol high")
    launcher, _ = fixture(tmp_path, monkeypatch, [record()], [
        event("task_started", turn_id="turn"),
        response("function_call_output", call_id="inner", output="visible result"),
        event("task_complete", turn_id="turn")], entries=[bad, launch(tmp_path)])
    result = reader.read(launcher, tmp_path)
    assert result.gaps
    assert "visible result" in json.dumps(reader.activity(result.turns[0][2]))


def test_hook_refused_launch_contributes_no_profile_source_or_gap(tmp_path, monkeypatch):
    blocked = launch(tmp_path, 9, call='blocked')
    blocked['message']['content'][0]['input']['command'] = 'uv run python scripts/codex_agent.py malformed'
    proof = {'type': 'user', 'timestamp': at(10), 'message': {'content': [{
        'type': 'tool_result', 'tool_use_id': 'blocked', 'is_error': True,
        'content': 'PreToolUse:Bash hook error: denied'}]}}
    launcher, _ = fixture(tmp_path, monkeypatch, [record()], [
        event('task_started', turn_id='turn'), event('task_complete', turn_id='turn')],
        entries=[blocked, proof, launch(tmp_path)])
    result = reader.read(launcher, tmp_path)
    assert result.coverage is reader.Coverage.ATTRIBUTED
    assert len(result.spend.sources) == 1
    assert result.spend.totals().total_tokens == 12
    assert len(result.turns) == 1


def test_recovery_refuses_ambiguous_or_conflicting_evidence(tmp_path, monkeypatch):
    launcher, path = fixture(tmp_path, monkeypatch, [], [
        event('task_started', turn_id='a'), event('task_complete', turn_id='a'),
        event('task_started', turn_id='b'), event('task_complete', turn_id='b')])
    (tmp_path / 'codex-session').write_text('thread\n')
    assert not spends.codex_spend({launcher: 'code-editor'}, before=20, home=tmp_path).sources[0].turn
    path.write_text('\n'.join(path.read_text().splitlines()[:2]) + '\n')
    events = tmp_path / 'codex-events.jsonl'
    for records in ([record(start=11), record(start=11)],
                    [dict(record(start=30), thread='other')]):
        events.write_text(''.join(json.dumps(r) + '\n' for r in records))
        result = spends.codex_spend({launcher: 'code-editor'}, before=20, home=tmp_path)
        assert result.sources[0].turn is None
    events.write_text('invalid\n')
    assert spends.codex_spend({launcher: 'code-editor'}, before=20, home=tmp_path).sources[0].turn is None


def test_recovered_usage_gaps_keep_activity_and_unfinished_tail(tmp_path, monkeypatch):
    launcher, path = fixture(tmp_path, monkeypatch, [], [
        event('task_started', turn_id='a'),
        response('function_call_output', call_id='inner', output='visible'),
        event('task_complete', turn_id='a')])
    (tmp_path / 'codex-session').write_text('thread\n')
    # A subsequent call bounds the lost wrapper without proving its completion.
    monkeypatch.setattr(measure, 'run_entries', lambda _: iter([
        launch(tmp_path), launch(tmp_path, 20, call='next')]))
    (tmp_path / 'codex-events.jsonl').unlink()
    result = reader.read(launcher, tmp_path)
    assert result.coverage is reader.Coverage.GAP
    assert result.turns[0][2].turn == 'a'
    assert result.turns[0][0].usage is None
    assert 'visible' in json.dumps(reader.activity(result.turns[0][2]))
    path.write_text('\n'.join(path.read_text().splitlines()[:2]) + '\n{"type":')
    result = reader.read(launcher, tmp_path)
    assert result.turns[0][0].running
    assert result.turns[0][2].ended is None
