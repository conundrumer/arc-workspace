import json

import pytest
from tests.conftest import script

trial = script('trial_agent')
codex = script('trial_codex')


def test_native_audit_and_barrier(tmp_path):
    path = tmp_path / 'trial.jsonl'
    events = [
        {'type': 'thread.started', 'thread_id': 'x'},
        {'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat case', 'aggregated_output': 'case', 'exit_code': 0}},
        {'type': 'future.tool', 'payload': 'unknown visible call'},
        {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'answer'}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'cached_input_tokens': 3, 'output_tokens': 2}},
    ]
    path.write_text(''.join(json.dumps(e) + '\n' for e in events))
    trial.cached(path)
    output = '\n'.join(trial.calls(path))
    assert all(json.dumps(e, ensure_ascii=False) in output for e in events)
    assert 'cached_input_tokens 3' in output
    assert 'cache_creation_input_tokens ?' in output


def test_failures_release_wait(tmp_path):
    path = tmp_path / 'trial.jsonl'
    path.write_text(json.dumps({'type': 'turn.failed', 'error': {'message': 'failed'}}) + '\n')
    with pytest.raises(trial.Refused):
        trial.cached(path)
    path.write_text('')
    codex.write_status(path, 1, 'process failed before events')
    with pytest.raises(trial.Refused):
        trial.cached(path)
    assert 'process failed before events' in '\n'.join(trial.calls(path))


def test_completion_without_reply_refuses(tmp_path):
    path = tmp_path / 'trial.jsonl'
    path.write_text(json.dumps({'type': 'turn.completed'}) + '\n')
    with pytest.raises(trial.Refused):
        trial.cached(path)
