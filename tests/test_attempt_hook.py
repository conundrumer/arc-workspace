"""Denied stops and failed tools cannot silently publish a lifecycle end."""

import io
import json

import pytest

from tests.conftest import script
from operations import attempts as a

hook = script('attempt_hook')
entry = script('hook_entry')
journal = script('attempt_record')


def test_denied_stop_and_main_stop_write_no_agent_stop(monkeypatch, capsys):
    monkeypatch.setattr(entry.sys, 'stdin', io.StringIO(json.dumps({
        'agent_id': 'worker', 'last_assistant_message': 'report'})))
    entry.run_subagent_stop('test', [lambda _: 'denied'])
    assert json.loads(capsys.readouterr().out)['decision'] == 'block'
    assert not journal.Record().events()
    monkeypatch.setattr(entry.sys, 'stdin', io.StringIO('{}'))
    entry.run_subagent_stop('test', [])
    assert not journal.Record().events()


def test_refused_task_stop_and_pretool_message_create_no_delivery():
    record = journal.Record()
    hook.tool({'hook_event_name': 'PostToolUseFailure', 'tool_name': 'TaskStop',
        'tool_use_id': 'kill', 'agent_id': 'parent', 'tool_input': {},
        'tool_response': {'agentId': 'worker', 'error': 'refused'}}, record)
    hook.tool({'hook_event_name': 'PreToolUse', 'tool_name': 'SendMessage'}, record)
    assert not record.events()


def test_refused_send_never_resumes_stopped_recipient():
    record = journal.Record()
    record.append(a.Stopped(source='stopped', at=1, agent='worker', text='report'))
    hook.tool({'hook_event_name': 'PostToolUseFailure', 'tool_name': 'SendMessage',
        'tool_use_id': 'send', 'agent_id': 'parent',
        'tool_input': {'recipient': 'worker', 'message': 'request'},
        'tool_response': {'success': False}}, record)
    assert a.fold(record.events())['worker'].stopped
    assert not a.fold(record.events())['worker'].outstanding
