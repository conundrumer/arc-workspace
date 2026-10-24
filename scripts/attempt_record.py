"""Durable attempt events, delivery preparation and per-seat admission.

The journal belongs to the main checkout. Reads never import, reconcile or
establish a lifecycle transition. Migration coverage is separate evidence.
"""

from controlled_markdown import mctx

import fcntl
import hashlib
import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from engine import checkout
from operations import attempts as a
from operations.roles import Described, Role


SEAT_BUSY = mctx('work call refused: seat {role} {subject} is busy; no thread or turn accepted; wait for its owner, then retry')


def busy(seat: Described):
    from codex_ticket import Refused
    return Refused(SEAT_BUSY.format(role=seat.role, subject=seat.subject))


def directory() -> Path:
    return checkout.main_worktree(checkout.ROOT) / '.attempts'


class Record:
    def __init__(self, path: Path | None = None):
        self.path = path or directory() / 'attempts.sqlite'

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events (source TEXT PRIMARY KEY, agent TEXT NOT NULL, recipient TEXT, kind TEXT NOT NULL, at REAL NOT NULL, data TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS identities (agent TEXT PRIMARY KEY, parent TEXT, role TEXT NOT NULL, subject TEXT NOT NULL, scratch TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS parents ON identities(parent)')
            db.execute('CREATE INDEX IF NOT EXISTS seats ON identities(role, subject)')
            db.execute('CREATE INDEX IF NOT EXISTS agents ON events(agent)')
            db.execute('CREATE INDEX IF NOT EXISTS recipients ON events(recipient)')
            db.execute('CREATE TABLE IF NOT EXISTS migration (ticket TEXT PRIMARY KEY, complete INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL, target TEXT NOT NULL, text TEXT NOT NULL, envelope TEXT NOT NULL, scratch TEXT NOT NULL)')
            with db:
                yield db
        finally:
            db.close()

    def append(self, *events: a.Event) -> None:
        with self.connect() as db:
            for event in events:
                data = json.dumps(asdict(event), sort_keys=True)
                old = db.execute('SELECT data FROM events WHERE source=?', (event.source,)).fetchone()
                if old is not None and old[0] != data:
                    raise ValueError(mctx('event source {source} already holds a different event').format(source=event.source))
                if isinstance(event, a.Launched):
                    db.execute('INSERT OR IGNORE INTO identities VALUES (?, ?, ?, ?, ?)',
                        (event.agent, event.parent, event.seat.role, event.seat.subject, event.scratch))
                db.execute('INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)',
                    (event.source, event.agent, event.recipient if isinstance(event, a.Message) else None,
                     type(event).__name__, event.at, data))

    def events(self, ids: Iterable[str] | None = None) -> tuple[a.Event, ...]:
        if not self.path.exists():
            return ()
        with sqlite3.connect(f'file:{self.path}?mode=ro', uri=True) as db:
            if ids is None:
                rows = db.execute('SELECT kind, data FROM events ORDER BY at, source').fetchall()
            else:
                selected = tuple(set(ids))
                if not selected:
                    return ()
                values = ','.join('(?)' for _ in selected)
                rows = db.execute(f"""WITH RECURSIVE selected(agent) AS (
                    VALUES {values}
                    UNION SELECT identities.agent FROM identities JOIN selected ON identities.parent=selected.agent
                    UNION SELECT events.recipient FROM events JOIN selected ON events.agent=selected.agent WHERE events.recipient IS NOT NULL
                    UNION SELECT events.agent FROM events JOIN selected ON events.recipient=selected.agent)
                    SELECT kind, data FROM events WHERE agent IN selected ORDER BY at, source""", selected).fetchall()
        kinds = {kind.__name__: kind for kind in a.EVENTS}
        events = []
        for kind, text in rows:
            value = json.loads(text)
            if kind == 'Launched':
                value['seat'] = Described(Role(value['seat']['role']), value['seat']['subject'])
                value['transport'] = a.Transport(value['transport'])
            if kind == 'TurnEnded':
                value['status'] = a.Terminal(value['status'])
            if kind == 'Message':
                value['outcome'] = a.Outcome(value['outcome'])
            events.append(kinds[kind](**value))
        return tuple(events)

    def acceptance(self, agent: str, reservation: str, at: float, thread: str, turn: str) -> a.Accepted:
        """Publish the immutable acceptance once, retaining its admitted identity."""
        known = [event for event in self.events([agent]) if isinstance(event, a.Accepted)
                 and event.agent == agent and (event.thread, event.turn) == (thread, turn)]
        event = known[0] if known else a.Accepted(source='accepted:' + reservation,
            agent=agent, at=at, reservation=reservation, thread=thread, turn=turn)
        self.append(event)
        return event

    def timestamp(self, source: str) -> float | None:
        if not self.path.exists():
            return None
        with sqlite3.connect(f'file:{self.path}?mode=ro', uri=True) as db:
            row = db.execute('SELECT at FROM events WHERE source=?', (source,)).fetchone()
        return row[0] if row is not None else None

    def admission(self, seat: Described, agent: str, reservation: str, revision: int,
                  at: float, launch: a.Launched, change: str | None = None) -> None:
        """Called under the seat lock before any transport submission."""
        projected = a.fold(self.events())
        for other in projected.values():
            if (other.coverage is not None and not other.coverage.complete
                    and other.coverage.change == (change or seat.subject)):
                from codex_ticket import Refused
                raise busy(seat)
            if other.launch is not None and other.launch.seat == seat and other.held:
                if other.agent != agent or other.unresolved != frozenset({reservation}):
                    from codex_ticket import Refused
                    raise busy(seat)
        self.append(launch, a.Reserved(source='reserved:' + reservation, at=at,
                    agent=agent, reservation=reservation, revision=revision))

    def prepare(self, delivery: str, sender: str, recipient: str, target: str,
                text: str, envelope: str, scratch: Path) -> None:
        with self.connect() as db:
            db.execute('INSERT INTO deliveries VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (delivery, sender, recipient, target, text, envelope, str(scratch)))

    def delivery(self, delivery: str) -> dict[str, str]:
        with sqlite3.connect(f'file:{self.path}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM deliveries WHERE id=?', (delivery,)).fetchone()
        if row is None:
            raise ValueError(mctx('unknown prepared delivery'))
        return dict(row)


def seat_path(seat: Described, record: Record | None = None) -> Path:
    base = (record or Record()).path.parent / 'seats'
    name = hashlib.sha256(json.dumps([seat.role, seat.subject]).encode()).hexdigest()
    return base / name


@contextmanager
def seat_lock(seat: Described, record: Record | None = None) -> Iterator[None]:
    path = seat_path(seat, record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            from codex_ticket import Refused
            raise busy(seat) from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def observe(action) -> None:
    """An observational failure preserves the action's result and ownership."""
    import sys
    try:
        action()
    except Exception as exc:
        print(f'attempt_record: observational write failed: {exc}', file=sys.stderr)


def open_changes(main: Path):
    from ticket_reads import read_tickets
    from ticketing.vocabulary import Kind, Status
    tickets, unread = read_tickets(main / 'tickets')
    if unread:
        raise ValueError('ticket history is unreadable: ' + ', '.join(str(x.path) for x in unread))
    return tuple(t for t in tickets.values() if t.kind is Kind.CHANGE
                 and t.status is not Status.CLOSED)


def resolve_seat(cwd: Path, role: Role, agent: str, assignment=None,
                 record: Record | None = None) -> Described | None:
    """Resolve all available identities; a known change tree cannot lose its seat."""
    from operations.worktrees import logged_worktree
    record = record or Record()
    candidates = set()
    if assignment is not None:
        candidates.add(assignment.seat)
    for event in record.events([agent]):
        if isinstance(event, a.Launched) and event.agent == agent:
            candidates.add(event.seat)
    main = checkout.main_worktree(cwd)
    changes = open_changes(main)
    matching = [t for t in changes if (path := logged_worktree(t)) is not None
                and path.resolve() == cwd.resolve()]
    if len(matching) > 1:
        raise ValueError(mctx('more than one open change logs this worktree'))
    if matching:
        candidates.add(Described(role, matching[0].number))
    known_tree = main / '.claude' / 'worktrees'
    if cwd.resolve().is_relative_to(known_tree.resolve()) and not candidates:
        raise ValueError(mctx('no open change logs this change worktree, and the call has no assignment or recorded launch'))
    if len(candidates) > 1:
        raise ValueError(mctx('the assignment, the recorded launch and the change that logs this worktree give different seats'))
    return next(iter(candidates)) if candidates else None


def lock_held(path: Path) -> bool:
    """A missing legacy lock is free; unreadable evidence raises."""
    if not path.exists():
        return False
    with path.open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock, fcntl.LOCK_UN)
    return False


def import_launcher(record: Record, agent: str, path: Path, home: Path,
                    preparing: Path | None = None) -> tuple[bool, list[str]]:
    from codex_agent import legacy_work_lock
    from codex_reads import calls
    from codex_transcript import read
    from run_reads import run_entries
    import codex_rollout

    entries = list(run_entries(path))
    gaps: list[str] = []
    work = calls(entries, gaps)
    current = next((call for call in reversed(work) if preparing is not None
                    and call.scratch.resolve() == preparing.resolve()), None)
    producer = any(lock_held(legacy_work_lock(call.scratch)) for call in work
                   if preparing is None or call.scratch.resolve() != preparing.resolve())
    transcript = read(path, home)
    prefix = f'{path}:{current.call_id}:' if current else None
    gaps.extend(gap for gap in transcript.gaps if prefix is None or not gap.startswith(prefix))
    accepted = set()
    for source, _, turn in transcript.turns:
        assert source.thread is not None
        token = 'legacy:' + agent + ':' + source.thread + ':' + turn.turn
        at = turn.started
        revision = 0
        for call in work:
            if source.source != f'{path}:{call.call_id}':
                continue
            from codex_ticket import Binding, Store
            binding = Binding.read(call.scratch)
            if binding is not None:
                state = Store(binding.store).snapshot()
                history = [*state.get('history', []), state['agents'][agent]]
                for item in history:
                    if (item.get('agent', agent) == agent and item['native'] == source.thread
                            and item['turn'] == turn.turn):
                        token, at, revision = item['token'], item['reserved'], item['revision']
            submission = call.scratch / 'attempt-submission.json'
            if submission.exists():
                saved = json.loads(submission.read_text())
                if saved['agent'] == agent and turn.started >= saved['at']:
                    token, at, revision = saved['reservation'], saved['at'], saved['revision']
        event = record.acceptance(agent, token, at, source.thread, turn.turn)
        token = event.reservation
        accepted.add((source.thread, turn.turn))
        if not any(isinstance(e, a.Reserved) and e.reservation == token for e in record.events([agent])):
            record.append(a.Reserved(source='reserved:' + token, at=event.at, agent=agent,
                                     reservation=token, revision=revision))
        if turn.ended is not None:
            status = a.Terminal.COMPLETED if turn.end_state is codex_rollout.TurnEnd.COMPLETE else a.Terminal.INTERRUPTED
            ended = next((e for e in record.events([agent]) if isinstance(e, a.TurnEnded)
                          and e.reservation == token), None)
            record.append(ended or a.TurnEnded(source='ended:' + token, at=turn.ended,
                agent=agent, reservation=token, status=status))
        else:
            producer = True
    for call in work:
        session = call.scratch / 'codex-session'
        if session.exists():
            thread = session.read_text().strip()
            turns = codex_rollout.turns(thread, home)
            for turn in turns:
                if (thread, turn.turn) not in accepted:
                    gaps.append('unattributed legacy accepted turn ' + turn.turn)
                if turn.ended is None:
                    producer = True
    return producer, gaps


def import_claude(record: Record, agent: str, path: Path, seat: Described,
                  parent: str | None, at: float, home: Path,
                  seen: set[str], preparing_agent: str | None = None,
                  preparing_scratch: Path | None = None, change: str | None = None) -> None:
    from agent_launches import launches
    from agent_reports import Sign
    from attempt_hook import tool
    from run_reads import agent_type, blocks, read_meta, results_by_call, run_entries
    from transcript_entries import epoch
    from operations.roles import CODEX_LAUNCHER, described

    if agent in seen:
        return
    seen.add(agent)
    events = record.events([agent])
    initial = next((e for e in events if isinstance(e, a.Launched) and e.agent == agent), None)
    kind = agent_type(path)
    if kind is None:
        raise ValueError(mctx('attempt transcript has no agent type'))
    record.append(initial or a.Launched(source='legacy-launch:' + agent, at=at,
        agent=agent, seat=seat, parent=parent, agent_type=kind, transport=a.Transport.CLAUDE))
    notes: list[str] = []
    producer = False
    try:
        entries = list(run_entries(path))
        results = results_by_call(entries)
        for entry in entries:
            if entry.get('type') != 'assistant' or not entry.get('timestamp'):
                continue
            for block in blocks(entry, 'tool_use'):
                if block.get('name') not in ('SendMessage', 'SubagentHandback', 'TaskStop'):
                    continue
                result = results.get(block['id'])
                if result is not None:
                    tool({'hook_event_name': 'PostToolUse', 'tool_name': block['name'],
                        'agent_id': agent, 'tool_use_id': block['id'],
                        'tool_input': block['input'], 'tool_response': result,
                        '_at': epoch(entry['timestamp'])}, record)
        for launch in launches(path, notes):
            if launch.agent is None or launch.path is None:
                notes.append('launch has no readable child identity: ' + launch.call)
                continue
            meta = read_meta(launch.path)
            description = described(meta['description']) if meta and 'description' in meta else None
            if description is None:
                continue
            import_claude(record, launch.agent, launch.path, description, agent,
                          launch.since, home, seen, preparing_agent, preparing_scratch, change)
            for entry in launch.entries:
                for who, sign in entry.signs:
                    if who not in (launch.agent, launch.call):
                        continue
                    if sign is Sign.STOPPED:
                        record.append(a.Stopped(source=f'legacy-stop:{launch.agent}:{entry.time}',
                            at=entry.time, agent=launch.agent, text=''))
                for report in entry.reports:
                    record.append(a.HandedBack(source=f'legacy-report:{launch.agent}:{report.time}',
                        at=report.time, agent=launch.agent, text=report.text))
        if agent_type(path) == CODEX_LAUNCHER:
            producer, gaps = import_launcher(record, agent, path, home,
                preparing_scratch if preparing_agent == agent else None)
            notes.extend(gaps)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        notes.append(str(exc))
        producer = True
    import time
    checked = time.time()
    record.append(a.Coverage(source=f'coverage:{agent}:{checked}', at=checked, agent=agent,
        complete=not notes, reason='; '.join(notes), producer=producer, change=change))


def backfill(record: Record, main: Path, home: Path, seat: Described | None = None,
             preparing_agent: str | None = None, preparing_scratch: Path | None = None,
             change: str | None = None) -> None:
    """Explicitly import available open-attempt history and retain each unresolved source."""
    import time
    from transcripts import find
    from run_reads import session_of, read_meta
    from tree_reads import scratch
    from codex_native_reads import native_assignments
    from codex_attempts import publish
    from codex_ticket import Store
    from operations.roles import described

    seen: set[str] = set()
    sessions: set[Path] = set()
    available = open_changes(main)
    with record.connect() as db:
        for ticket in available:
            db.execute('INSERT OR IGNORE INTO migration VALUES (?, 0)', (ticket.number,))
    changes = [t for t in available if seat is None or t.number == (change or seat.subject)]
    for ticket in changes:
        operators = {line.agent_id for line in ticket.log if line.agent_id and line.agent == 'operator'}
        for operator in sorted(operators):
            try:
                path = find(operator)
                sessions.add(scratch(session_of(path).name))
                meta = read_meta(path)
                description = described(meta['description']) if meta and 'description' in meta else None
                import_claude(record, operator, path, description or Described(Role.OPERATOR, ticket.number),
                              None, ticket.filed, home, seen, preparing_agent, preparing_scratch, ticket.number)
            except (OSError, ValueError, KeyError) as exc:
                at = time.time()
                record.append(a.Launched(source='legacy-missing:' + operator, at=ticket.filed,
                    agent=operator, seat=Described(Role.OPERATOR, ticket.number), parent=None,
                    agent_type='operator', transport=a.Transport.CLAUDE),
                    a.Coverage(source=f'coverage:{operator}:{at}', at=at, agent=operator,
                        complete=False, reason=str(exc), producer=True, change=ticket.number))
    with record.connect() as db:
        for ticket in changes:
            db.execute('UPDATE migration SET complete=1 WHERE ticket=?', (ticket.number,))
    allowed = {t.number for t in changes}
    for session in sorted(sessions):
        for native in native_assignments(session, include_history=True):
            assignment, item = native.assignment, native.state
            if assignment.ticket not in allowed:
                continue
            notes = []
            try:
                publish(Store(native.store), {'agents': {assignment.agent: item}})
                if item['phase'] == 'reserved' or (item['phase'] != 'ended' and item['turn'] is None):
                    notes.append('native submission has no resolved acceptance')
            except (OSError, ValueError, KeyError) as exc:
                notes.append(str(exc))
            at = time.time()
            record.append(a.Coverage(source=f'coverage:{assignment.agent}:{at}', at=at,
                agent=assignment.agent, complete=not notes, reason='; '.join(notes),
                producer=item['phase'] != 'ended', change=assignment.ticket))


def check_coverage(record: Record) -> tuple[str, ...]:
    """Read only: unknown or potentially old producers prevent cutover."""
    projected = a.fold(record.events())
    notes = []
    if not record.path.exists():
        return ('migration has not imported the open attempts',)
    with sqlite3.connect(f'file:{record.path}?mode=ro', uri=True) as db:
        targets = db.execute('SELECT ticket, complete FROM migration').fetchall()
    notes.extend(ticket + ': history has not been imported' for ticket, complete in targets if not complete)
    for attempt in projected.values():
        coverage = attempt.coverage
        if coverage is None or not coverage.complete or coverage.producer:
            notes.append(attempt.agent + ': ' + ('history has no coverage evidence' if coverage is None
                else coverage.reason or 'an old producer may still write'))
        elif attempt.unresolved:
            notes.append(attempt.agent + ': unresolved imported reservations or turns')
    return tuple(notes)


def main() -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    migration = commands.add_parser('backfill')
    migration.add_argument('--check', action='store_true')
    args = parser.parse_args()
    record = Record()
    try:
        if not args.check:
            backfill(record, checkout.main_worktree(checkout.ROOT), Path.home())
        notes = check_coverage(record)
        if notes:
            print('\n'.join(notes), file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'attempt_record: {exc}', file=sys.stderr)
        return 1


def acknowledge_input(record: Record, agent: str, prompt: str, thread: str, turn: str,
                      revision: int, at: float) -> None:
    """Consume full eligible messages once per occurrence in accepted input."""
    import re
    normalize = lambda text: re.sub(r'\s+', ' ', text).strip()
    projection = a.fold(record.events([agent]))
    attempt = projection.get(agent)
    if attempt is None:
        return
    normalized = normalize(prompt)
    consumed: dict[str, int] = {}
    for message in attempt.outstanding:
        text = normalize(message.text)
        if not text or message.agent not in normalized:
            continue
        used = consumed.get(text, 0)
        pattern = (r'(?<!\w)' if text[0].isalnum() else '') + re.escape(text) + (r'(?!\w)' if text[-1].isalnum() else '')
        if len(list(re.finditer(pattern, normalized))) <= used:
            continue
        consumed[text] = used + 1
        record.append(a.Received(source='received:' + message.delivery, at=at,
            agent=agent, delivery=message.delivery, revision=revision, thread=thread, turn=turn))


if __name__ == '__main__':
    raise SystemExit(main())
