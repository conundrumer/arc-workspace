"""Publication of committed native ticket transitions to the attempt journal."""

from pathlib import Path
from typing import Any

from attempt_record import Record, observe, seat_lock
from operations import attempts as a
from operations.roles import Described


def publish(store, state: dict[str, Any]) -> None:
    from codex_ticket import Assignment, Phase

    record = Record()
    events: list[a.Event] = []
    for agent, item in state['agents'].items():
        assignment = Assignment.read(store.manifest(agent, item['revision']))
        token = item['token']
        common = dict(agent=agent, at=item['reserved'])
        recorded = record.events([agent])
        existing = next((e for e in recorded if isinstance(e, a.Launched) and e.agent == agent), None)
        events.extend([
            existing or a.Launched(source='native-launch:' + agent, agent=agent,
                at=item.get('launched', item['reserved']),
                seat=assignment.seat,
                parent=item['parent'] or assignment.operator,
                agent_type=assignment.actual_type, transport=a.Transport.NATIVE,
                scratch=str(assignment.scratch)),
            a.Reserved(source='reserved:' + token, reservation=token,
                revision=item['revision'], **common)])
        if item['revision'] > 1:
            events.append(a.Resumed(source='resume:' + token,
                parent=item['parent'] or assignment.operator, **common))
        if item['native'] is not None and item['turn'] is not None:
            acceptance = record.acceptance(agent, token, item['reserved'], item['native'], item['turn'])
            if item.get('runtime') is not None:
                source = 'runtime:' + agent + ':' + item['runtime']
                bound = next((e for e in recorded if isinstance(e, a.RuntimeBound) and e.source == source), None)
                events.append(bound or a.RuntimeBound(source=source,
                    agent=agent, at=acceptance.at, thread=item['native'], runtime=item['runtime']))
        if item['phase'] == Phase.ENDED:
            if item.get('refused'):
                events.append(a.Refused(source='refused:' + token, reservation=token, **common))
            else:
                events.append(a.TurnEnded(source='ended:' + token, reservation=token,
                    status=a.Terminal(item['status']), **common))
        if item['phase'] == Phase.INTERRUPTING:
            events.append(a.Interrupted(source='interrupted:' + token, reservation=token, **common))
        if item.get('validated') and 'receipt' in item:
            receipt = item['receipt']
            from codex_reports import digest
            if receipt['revision'] != item['revision'] or receipt['inputs_digest'] != assignment.inputs_digest:
                raise ValueError('validated receipt differs from its assignment')
            data = assignment.report.read_bytes() if assignment.report.exists() else None
            text = data.decode() if data is not None and digest(data) == receipt['report_digest'] else None
            old_report = next((e for e in recorded if isinstance(e, a.Reported)
                               and e.source == 'report:' + token and e.digest == receipt['report_digest']), None)
            events.append(old_report or a.Reported(source='report:' + token, revision=item['revision'],
                digest=receipt['report_digest'], text=text, **common))
    for delivery, receipt in state.get('deliveries', {}).items():
        prepared = record.delivery(delivery)
        events.append(a.Received(source='received:' + delivery, agent=prepared['recipient'],
            delivery=delivery, **receipt))
    record.append(*events)


def committed(store, state: dict[str, Any]) -> None:
    observe(lambda: publish(store, state))
