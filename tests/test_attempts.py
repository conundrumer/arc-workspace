"""Journal refusal, delivery and publication failures that would otherwise be silent."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import script
from tests.test_codex_ticket import assignment
from operations import attempts as a
from operations.roles import Described, Role

journal = script('attempt_record')
ticket = script('codex_ticket')
delivery = script('codex_delivery')


def test_seat_survives_publication_failure_and_roles_are_independent(tmp_path, monkeypatch, capsys):
    first = ticket.Store(tmp_path / 'first')
    root = assignment(tmp_path, first)
    token = first.reserve(root)
    location = journal.directory()
    monkeypatch.setattr(journal, 'directory', lambda: tmp_path / 'blocked' / 'journal')
    (tmp_path / 'blocked').write_text('not a directory')
    first.accepted(root.agent, token, 'thread', 'turn')
    assert first.snapshot()['agents'][root.agent]['phase'] == 'running'
    assert capsys.readouterr().err
    monkeypatch.setattr(journal, 'directory', lambda: location)
    second = ticket.Store(tmp_path / 'second')
    other = assignment(tmp_path, second)
    with pytest.raises(ticket.Refused):
        second.reserve(other)
    independent = assignment(tmp_path, second, Role.DOC_EDITOR)
    second.reserve(independent)


def test_locked_seat_refuses_before_store_reservation(tmp_path):
    store = ticket.Store(tmp_path / 'store')
    root = assignment(tmp_path, store)
    before = store.snapshot()
    with journal.seat_lock(Described(root.role, root.ticket)):
        with pytest.raises(ticket.Refused):
            store.reserve(root)
    assert store.snapshot() == before


def test_messages_survive_omitted_turn_and_equal_text_requires_an_occurrence(tmp_path):
    record = journal.Record()
    for index in range(2):
        record.append(a.Message(source=f'send{index}', at=index, agent='sender',
            recipient='worker', text='complete message', outcome=a.Outcome.ACCEPTED,
            delivery=str(index), call=str(index)))
    journal.acknowledge_input(record, 'worker', 'sender: unrelated input', 'thread', 'omitted', 1, 3)
    assert len(a.fold(record.events())['worker'].outstanding) == 2
    journal.acknowledge_input(record, 'worker', 'sender: complete message', 'thread', 'consuming', 2, 4)
    attempt = a.fold(record.events())['worker']
    assert len(attempt.outstanding) == 1
    assert [r.turn for r in attempt.receipts] == ['consuming']
    before = record.path.read_bytes()
    record.events()
    journal.check_coverage(record)
    assert record.path.read_bytes() == before


def row(at, kind, payload):
    return json.dumps({'type': kind, 'timestamp': datetime.fromtimestamp(at, timezone.utc).isoformat(),
                       'payload': payload}) + '\n'


def native_tree(tmp_path):
    store = ticket.Store(tmp_path / 'store')
    parent = assignment(tmp_path, store)
    token = store.reserve(parent)
    store.accepted(parent.agent, token, 'parent', 'parent-turn')
    child = assignment(tmp_path, store, Role.ITEM_CHECKER)
    token = store.reserve(child, parent.agent)
    store.accepted(child.agent, token, 'child', 'child-turn', '/root/' + child.agent)
    reserved = store.snapshot()['agents'][child.agent]['reserved']
    directory = tmp_path / '.codex' / 'sessions'
    directory.mkdir(parents=True)
    path = directory / 'rollout-test-child.jsonl'
    path.write_text(row(reserved + 1, 'session_meta', {'id': 'child', 'source': {
        'subagent': {'thread_spawn': {'parent_thread_id': 'parent'}}}})
        + row(reserved + 2, 'event_msg', {'type': 'task_started', 'turn_id': 'child-turn'})
        + row(reserved + 3, 'response_item', {'type': 'agent_message',
            'recipient': '/root/' + child.agent, 'content': [{'type': 'encrypted_content', 'data': 'opaque'}]}))
    return store, parent, child, path


@pytest.mark.parametrize('accepted', [True, False])
def test_encrypted_midturn_receipt_needs_accepted_send_and_preserves_first_turn(tmp_path, accepted):
    store, parent, child, path = native_tree(tmp_path)
    prepared = delivery.message(parent.scratch, child.agent, {'message': 'complete message'})
    first = delivery.received(child.scratch, prepared['delivery'], tmp_path)
    record = journal.Record()
    assert not any(isinstance(e, a.Message) for e in record.events())
    with pytest.raises(ticket.Refused):
        delivery.received(parent.scratch, prepared['delivery'], tmp_path)
    at = store.snapshot()['agents'][parent.agent]['reserved'] + 5
    root = path.parent / 'rollout-test-parent.jsonl'
    manifest = store.manifest(parent.agent, 1)
    root.write_text(row(at, 'event_msg', {'type': 'task_started', 'turn_id': 'parent-turn'})
        + row(at + 1, 'event_msg', {'type': 'user_message', 'message': f'{manifest}\n{parent.brief.read_text()}'})
        + row(at + 2, 'response_item', {'type': 'function_call', 'name': 'collaboration.send_message',
            'call_id': 'actual-send', 'arguments': json.dumps(prepared['call'])})
        + row(at + 3, 'response_item', {'type': 'function_call_output', 'call_id': 'actual-send',
            'output': json.dumps({'status': 'sent'} if accepted else {'error': 'refused'})}))
    delivery.reconcile_messages(store, parent.agent, tmp_path)
    assert not a.fold(record.events())[child.agent].outstanding
    messages = [e for e in record.events() if isinstance(e, a.Message)]
    assert messages[0].outcome is (a.Outcome.ACCEPTED if accepted else a.Outcome.REFUSED)
    store.ended(child.agent, 'child-turn', 'completed')
    assert delivery.received(child.scratch, prepared['delivery'], tmp_path) == first


def test_new_receipt_refuses_ended_execution(tmp_path):
    store, parent, child, _ = native_tree(tmp_path)
    prepared = delivery.message(parent.scratch, child.agent, {'message': 'message'})
    store.ended(child.agent, 'child-turn', 'completed')
    with pytest.raises(ticket.Refused):
        delivery.received(child.scratch, prepared['delivery'], tmp_path)


def test_check_without_import_refuses_and_creates_nothing(tmp_path):
    path = tmp_path / 'uncreated' / 'journal.sqlite'
    assert journal.check_coverage(journal.Record(path))
    assert not path.parent.exists()


def test_admitted_acceptance_is_one_fact_across_publication_and_import(tmp_path):
    import time
    agent = script('codex_agent')
    store = ticket.Store(tmp_path / 'store')
    root = assignment(tmp_path, store)
    record = journal.Record()
    at = time.time()
    token = 'admitted-reservation'
    launch = a.Launched(source='launch', at=at, agent=root.agent, seat=root.seat,
        parent=root.operator, agent_type=root.actual_type, transport=a.Transport.NATIVE,
        scratch=str(root.scratch))
    with journal.seat_lock(root.seat):
        record.admission(root.seat, root.agent, token, root.revision, at, launch)
        store.reserve(root, reservation=token)
    (root.scratch / 'attempt-submission.json').write_text(json.dumps(dict(
        agent=root.agent, reservation=token, at=at, revision=root.revision)))
    store.accepted(root.agent, token, 'thread', 'turn')
    agent.publish_accepted(root.scratch, 'thread', 'turn', 'input')
    before = [e for e in record.events() if isinstance(e, a.Accepted)]
    assert len(before) == 1
    child = assignment(tmp_path, store, Role.ITEM_CHECKER)
    child_token = store.reserve(child, root.agent)
    store.accepted(child.agent, child_token, 'child-thread', 'child-turn', '/root/child')
    assert [e for e in record.events([root.agent]) if isinstance(e, a.Accepted)
            and e.agent == root.agent] == before
    assert any(isinstance(e, a.RuntimeBound) and e.agent == root.agent and e.runtime == '/root'
               for e in record.events())
    store.ended(child.agent, 'child-turn', 'completed')
    store.ended(root.agent, 'turn', 'completed')
    (root.scratch / 'codex-session').write_text('thread')
    (root.scratch / 'codex-events.jsonl').write_text(json.dumps(dict(
        thread='thread', turn='turn', started=at + 1, ended=at + 2,
        running=False, usage=None, usage_reason='unavailable', output='')) + '\n')
    directory = tmp_path / '.codex' / 'sessions'
    directory.mkdir(parents=True)
    (directory / 'rollout-test-thread.jsonl').write_text(
        row(at + 1, 'event_msg', {'type': 'task_started', 'turn_id': 'turn'})
        + row(at + 2, 'event_msg', {'type': 'task_complete', 'turn_id': 'turn'}))
    transcript = tmp_path / 'launcher.jsonl'
    command = f'uv run python scripts/codex_agent.py code-editor {root.scratch} {root.brief} model high --agent-id {root.agent}'
    transcript.write_text(json.dumps({'type': 'assistant', 'uuid': 'launch', 'parentUuid': None,
        'timestamp': datetime.fromtimestamp(at - 1, timezone.utc).isoformat(), 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'id': 'work-call', 'input': {'command': command}}]}}) + '\n')
    assert len(script('codex_transcript').read(transcript, tmp_path).turns) == 1
    journal.import_launcher(record, root.agent, transcript, tmp_path)
    journal.import_launcher(record, root.agent, transcript, tmp_path)
    assert [e for e in record.events() if isinstance(e, a.Accepted) and e.agent == root.agent] == before
    assert not a.fold(record.events())[root.agent].unresolved
