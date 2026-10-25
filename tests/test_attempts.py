"""Journal refusal, delivery and publication failures that would otherwise be silent."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import script
from tests.test_codex_ticket import assignment
from operations import attempts as a
from operations.roles import Described, Role
from operations.state import Agent, Ended, Report, Running, Unknown, Waits

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


def launched(agent, seat, source, at, parent='op', native=False):
    return a.Launched(source=source, at=at, agent=agent, seat=seat, parent=parent,
        agent_type='code-editor', transport=a.Transport.NATIVE if native else a.Transport.CLAUDE)


def covered(agent, at=9.0, complete=True, producer=False):
    return a.Coverage(source=f'coverage:{agent}', at=at, agent=agent, complete=complete,
        reason='' if complete else 'a gap', producer=producer)


LOG = '\n\n## Log\n2026-10-17T00:00:00Z draft [ticket-analyst]: filed\n'


def write_ticket(main, status, number, *lines):
    (main / 'tickets' / status).mkdir(parents=True, exist_ok=True)
    (main / 'tickets' / status / f'{number}_change_x_coordinator.md').write_text(
        '---\nkind: change\n---\n# t: w\n\n## Motivation\n- m.' + LOG + ''.join(line + '\n' for line in lines))


CLOSED = '2026-10-22T00:00:00Z closed [coordinator]: fixed: done'
LAUNCH_TIME = datetime(2026, 10, 21, tzinfo=timezone.utc).timestamp()
START = datetime(2026, 10, 24, tzinfo=timezone.utc).timestamp()


def test_check_lists_only_what_the_migration_targets_and_a_state_read_would_hold(tmp_path):
    main = tmp_path / 'main'
    write_ticket(main, 'closed', '9-1', CLOSED)
    closed, open_ = Described(Role.CODE_EDITOR, '9-1'), Described(Role.CODE_EDITOR, '9-2')
    record = journal.Record()
    record.append(
        launched('hook', open_, 'claude:op:call', START + 5),
        launched('old-closed', closed, 'legacy-launch:old-closed', LAUNCH_TIME), covered('old-closed', complete=False),
        launched('old-open', open_, 'legacy-launch:old-open', LAUNCH_TIME), covered('old-open', complete=False),
        launched('no-coverage', open_, 'legacy-launch:no-coverage', LAUNCH_TIME),
        launched('producer', open_, 'legacy-launch:producer', LAUNCH_TIME), covered('producer', producer=True),
        launched('running', open_, 'legacy-launch:running', LAUNCH_TIME), covered('running'),
        launched('stopped', open_, 'legacy-launch:stopped', LAUNCH_TIME), covered('stopped'),
        a.Stopped(source='stop:stopped', at=LAUNCH_TIME + 1, agent='stopped', text=''),
        launched('pending', closed, 'legacy-launch:pending', LAUNCH_TIME), covered('pending'),
        a.Reserved(source='reserved:pending', at=LAUNCH_TIME + 1, agent='pending', reservation='r', revision=1),
        launched('native-old', open_, 'native-launch:native-old', START - 5, native=True),
        launched('native-new', open_, 'native-launch:native-new', START + 5, native=True),
        a.Message(source='m', at=START + 6, agent='main', recipient='old-open', text='x',
                  outcome=a.Outcome.ACCEPTED, delivery='d', call='c'),
        a.Stopped(source='stop:socket', at=START + 7, agent='socket', text=''),
        covered('no-launch', complete=False),
        *(a.Resumed(source=f'resume:{agent}', at=START + 8, agent=agent, parent='op')
          for agent in ('old-open', 'no-coverage', 'producer', 'running', 'native-old')))
    lines = journal.check_coverage(record, main)
    assert sorted(line.split(':')[0] for line in lines) == sorted(
        ['old-open', 'no-coverage', 'producer', 'running', 'pending', 'native-old', 'no-launch'])


def test_check_lists_no_imported_attempt_whose_record_shows_nothing_since_the_record_began(tmp_path):
    seat = Described(Role.DOC_REVIEWER, 'doc-review/x')
    record = journal.Record()
    record.append(
        launched('hook', seat, 'claude:op:call', START),
        launched('gap', seat, 'legacy-launch:gap', LAUNCH_TIME), covered('gap', at=START + 1, complete=False),
        launched('open', seat, 'legacy-launch:open', LAUNCH_TIME), covered('open'))
    assert journal.check_coverage(record, tmp_path / 'main') == ()
    record.append(a.Stopped(source='stop:gap', at=START + 2, agent='gap', text=''),
                  a.Resumed(source='resume:open', at=START + 2, agent='open', parent='op'))
    assert sorted(line.split(':')[0] for line in journal.check_coverage(record, tmp_path / 'main')) == ['gap', 'open']


def test_check_lists_an_incomplete_import_where_the_record_holds_no_launch_of_the_hook(tmp_path):
    seat = Described(Role.DOC_REVIEWER, 'doc-review/x')
    record = journal.Record()
    record.append(launched('gap', seat, 'legacy-launch:gap', LAUNCH_TIME), covered('gap', complete=False))
    assert [line.split(':')[0] for line in journal.check_coverage(record, tmp_path / 'main')] == ['gap']


def test_check_lists_each_migration_row_not_complete(tmp_path):
    record = journal.Record()
    record.append(launched('hook', Described(Role.CODE_EDITOR, '9-2'), 'claude:op:call', START))
    with record.connect() as db:
        db.execute("INSERT INTO migration VALUES ('9-2', 0), ('s1', 1)")
    assert journal.check_coverage(record, tmp_path / 'main') == ('9-2: history has not been imported',)


def test_the_events_of_an_attempt_fold_as_the_whole_record_folds_them(tmp_path):
    seat = Described(Role.CODE_EDITOR, '9-1')
    record = journal.Record()
    record.append(
        launched('parent', seat, 'l1', 1.0), launched('child', seat, 'l2', 2.0, parent='parent'),
        launched('grandchild', seat, 'l3', 3.0, parent='child'), launched('other', seat, 'l4', 4.0),
        a.Message(source='m1', at=5.0, agent='other', recipient='child', text='go',
                  outcome=a.Outcome.ACCEPTED, delivery='d1', call='c1'),
        a.Message(source='m2', at=6.0, agent='child', recipient='other', text='back',
                  outcome=a.Outcome.ACCEPTED, delivery='d2', call='c2'),
        a.Stopped(source='s1', at=7.0, agent='other', text=''),
        a.Stopped(source='s2', at=8.0, agent='grandchild', text=''))
    whole, part = a.fold(record.events()), a.fold(record.events(['parent']))
    for agent in ('parent', 'child', 'grandchild'):
        assert part[agent] == whole[agent]
    assert not any(e.agent == 'other' and not isinstance(e, a.Message) for e in record.events(['parent']))
    assert part['child'].inbound == whole['child'].inbound != ()


def test_a_second_reading_of_a_report_adds_nothing_and_fails_nothing(tmp_path):
    AgentEntry, Launch = script('agent_reports').AgentEntry, script('agent_launches').Launch
    record = journal.Record()

    def reading(text):
        entry = AgentEntry(10.0, (Report(10.0, text),), (), False, (), ())
        return Launch('child', None, 1.0, None, 'call', (entry,))

    journal.import_signs(record, reading('first'))
    journal.import_signs(record, reading('second'))
    journal.import_signs(record, reading('first'))
    assert [e.text for e in record.events() if isinstance(e, a.HandedBack)] == ['first']


def stamp(day, second=0):
    return datetime(2026, 10, day, 0, 0, second, tzinfo=timezone.utc).isoformat()


def entry(kind, day, body, uuid, parent=None):
    return {'type': kind, 'timestamp': stamp(day), 'uuid': uuid, 'parentUuid': parent, **body}


def said(day, uuid, text='brief'):
    return entry('user', day, {'message': {'content': text}}, uuid)


def tool_call(day, uuid, block):
    return entry('assistant', day, {'message': {'content': [{'type': 'tool_use', **block}]}}, uuid)


def tool_result(day, uuid, call, **result):
    return entry('user', day, {'toolUseResult': result, 'message': {'content': [
        {'type': 'tool_result', 'tool_use_id': call, 'content': 'ok'}]}}, uuid)


class Claude:
    """A Claude projects directory under `tmp_path` and the main checkout's tickets."""

    def __init__(self, tmp_path, monkeypatch):
        self.projects = tmp_path / 'claude' / 'projects'
        self.main = tmp_path / 'main'
        self.tmp_path = tmp_path
        monkeypatch.setattr(script('transcripts'), 'project_dirs', lambda: [self.projects])
        monkeypatch.setattr(script('tree_reads'), 'SCRATCH_ROOT', tmp_path / 'scratch')
        write_ticket(self.main, 'closed', '9-1', CLOSED)

    def session(self, name, *entries):
        path = self.projects / 'p' / f'{name}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries))

    def agent(self, session, agent, kind, description, *entries, call=None):
        path = self.projects / 'p' / session / 'subagents' / f'agent-{agent}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(e) + '\n' for e in entries))
        meta = {'description': description, **({'agentType': kind} if kind else {}),
                **({'toolUseId': call} if call else {})}
        path.with_suffix('.meta.json').write_text(json.dumps(meta))

    def operator(self, session, agent, day, *launches):
        """An operator that ran the command at `day` and launched each of `launches`:
        (child, call, description) at day 21."""
        calls = []
        for child, call, description in launches:
            calls.append(tool_call(21, f'{call}-call', {'id': call, 'name': 'Agent', 'input': {
                'description': description, 'prompt': 'p', 'subagent_type': 'x'}}))
            calls.append(tool_result(21, f'{call}-result', call, status='async_launched', agentId=child))
        self.agent(session, agent, Role.OPERATOR.agent_type, 'op operator 9-1', said(day, agent + '-0'),
            tool_call(day, agent + '-run', {'id': 'run', 'name': 'Bash', 'input': {
                'command': 'uv run python scripts/operate.py next'}}), *calls)

    def backfill(self, **options):
        script('state_reads').new_state()
        record = journal.Record()
        journal.backfill(record, self.main, self.tmp_path, **options)
        script('state_reads').new_state()
        return record

    def state(self, record, agent, seat, ticket='9-1'):
        operator_state = script('operator_state')
        built = Agent(agent, 'op', seat.role, seat.subject, '', LAUNCH_TIME, LAUNCH_TIME,
                      Running(Waits.AT_WORK), (), True)
        closes = operator_state.closes_of(journal.read_all_tickets(self.main))
        return operator_state.attempt_reads([built], closes=closes, home=self.tmp_path).agents[0].state


@pytest.fixture
def claude(tmp_path, monkeypatch):
    return Claude(tmp_path, monkeypatch)


def complete(attempt):
    """Whether the coverage of `attempt` is complete."""
    return attempt.coverage is not None and attempt.coverage.complete


def source(attempt):
    """The source of the launch of `attempt`."""
    return attempt.launch.source if attempt.launch is not None else None


def stranded(claude):
    """The record of the attempts imported for a session that ran on both sides of the
    record's start, whose operator launched a child of a closed change that fails to
    import, a child that imports, and a Codex launcher whose scratch directory is gone."""
    gone = claude.tmp_path / 'gone-scratch'
    command = f'uv run python scripts/codex_agent.py code-editor {gone} {gone}.md model high --agent-id c3'
    claude.session('s1', said(20, 's1-0'), said(25, 's1-1'))
    claude.operator('s1', 'op1', 20, ('c1', 't1', 'op code-editor 9-2'), ('c2', 't2', 'op code-editor 9-1'),
                    ('c3', 't3', 'op code-editor 9-1'))
    claude.agent('s1', 'c1', None, 'op code-editor 9-2', said(21, 'c1-0'), call='t1')
    claude.agent('s1', 'c2', 'code-editor', 'op code-editor 9-1', said(21, 'c2-0'), call='t2')
    claude.agent('s1', 'c3', 'codex-launcher', 'op code-editor 9-1', said(21, 'c3-0'),
                 tool_call(21, 'c3-1', {'id': 'work', 'name': 'Bash', 'input': {'command': command}}), call='t3')
    claude.session('s2', said(20, 's2-0'), said(22, 's2-1'))
    claude.operator('s2', 'op2', 20)
    claude.session('s3', said(25, 's3-0'))
    claude.operator('s3', 'op3', 25)
    journal.Record().append(launched('hook', Described(Role.CODE_EDITOR, '9-2'), 'claude:op:call', START))
    return claude.backfill()


def test_a_backfill_imports_the_operators_of_a_session_that_ran_on_both_sides_of_the_record(claude):
    record = stranded(claude)
    imported = {e.agent for e in record.events() if isinstance(e, a.Launched)}
    assert {'op1', 'c1', 'c2', 'c3'} <= imported
    assert not imported & {'op2', 'op3'}
    assert not any(row[1] == 0 for row in sqlite3.connect(record.path).execute('SELECT * FROM migration'))


def test_a_child_whose_import_fails_is_recorded_alone_and_the_launches_after_it_import(claude):
    record = stranded(claude)
    attempts = a.fold(record.events())
    assert [(agent, source(attempts[agent]), complete(attempts[agent])) for agent in ('c1', 'c2', 'op1')] == [
        ('c1', 'legacy-missing:c1', False), ('c2', 'legacy-launch:c2', True), ('op1', 'legacy-launch:op1', True)]


def test_a_child_of_a_closed_change_reads_ended_with_its_scratch_directory_gone(claude):
    record = stranded(claude)
    seat = Described(Role.CODE_EDITOR, '9-1')
    assert not complete(a.fold(record.events())['c3'])
    assert isinstance(claude.state(record, 'c2', seat), Ended)
    assert isinstance(claude.state(record, 'c3', seat), Ended)
    assert isinstance(claude.state(record, 'c1', Described(Role.CODE_EDITOR, '9-2')), Ended)
    assert journal.check_coverage(record, claude.main) == ()


@pytest.mark.parametrize('seat', [None, Described(Role.OPERATOR, '9-9')])
def test_a_backfill_with_no_seat_imports_the_native_assignment_of_a_closed_ticket(
        claude, tmp_path, monkeypatch, seat):
    write_ticket(claude.main, 'assigned', '9-9', '2026-10-20T00:00:00Z assigned [operator a00000000000000a1]: taken')
    claude.session('s1', said(20, 's1-0'))
    claude.operator('s1', 'a00000000000000a1', 20)
    elsewhere = tmp_path / 'elsewhere'
    monkeypatch.setattr(journal, 'directory', lambda: elsewhere)
    store = ticket.Store(tmp_path / 'store')
    root = assignment(tmp_path, store)
    token = store.reserve(root)
    store.accepted(root.agent, token, 'thread', 'turn')
    store.ended(root.agent, 'turn', 'completed')
    ticket.register(store.path, script('tree_reads').scratch('s1'), root.agent)
    monkeypatch.setattr(journal, 'directory', lambda: tmp_path / '.attempts')
    assert not any(e.agent == root.agent for e in journal.Record().events())
    record = claude.backfill(seat=seat)
    published = [e for e in record.events([root.agent]) if isinstance(e, a.Launched)]
    assert bool(published) is (seat is None)
    if seat is None:
        assert [e.change for e in record.events([root.agent]) if isinstance(e, a.Coverage)] == [root.ticket]



def test_a_child_whose_metadata_cannot_be_read_is_recorded_alone_and_listed_by_the_check(claude):
    write_ticket(claude.main, 'assigned', '9-9', '2026-10-20T00:00:00Z assigned [operator a00000000000000a1]: taken')
    claude.session('s1', said(20, 's1-0'))
    claude.operator('s1', 'a00000000000000a1', 20, ('c4', 't4', 'op code-editor 9-2'), ('c5', 't5', 'op code-editor 9-1'))
    claude.agent('s1', 'c4', 'code-editor', 'op code-editor 9-2', said(21, 'c4-0'), call='t4')
    claude.agent('s1', 'c5', 'code-editor', 'op code-editor 9-1', said(21, 'c5-0'), call='t5')
    (claude.projects / 'p' / 's1' / 'subagents' / 'agent-c4.meta.json').write_text('{')
    record = claude.backfill()
    attempts = a.fold(record.events())
    assert [(agent, source(attempts[agent]), complete(attempts[agent])) for agent in ('c4', 'c5', 'a00000000000000a1')] == [
        ('c4', 'legacy-missing:c4', False), ('c5', 'legacy-launch:c5', True),
        ('a00000000000000a1', 'legacy-launch:a00000000000000a1', True)]
    assert [line.split(':')[0] for line in journal.check_coverage(record, claude.main)] == ['c4']
