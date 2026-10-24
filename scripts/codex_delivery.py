"""Prepared native delivery and acknowledgements bound to accepted execution."""

import re
import secrets
import time
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from attempt_record import Record
from operations import attempts as a

ENVELOPE = mctx(
    'Delivery id: `{delivery}`. When you take this message, run '
    '`uv run python scripts/codex_ticket.py received {scratch} {delivery}`. '
    'Read [Receiving messages](prompts/agents/notes/native-agents.md#receiving-messages).')


RECONCILE = mctx('uv run python scripts/codex_ticket.py reconcile {scratch} {sender} {native}')


def message(scratch: Path, recipient: str, parameters: dict[str, Any]) -> dict[str, Any]:
    from codex_ticket import Assignment, Refused, bound

    binding, store = bound(scratch)
    target = store.target(binding.agent, recipient)
    state = store.snapshot()
    matches = [aid for aid, item in state['agents'].items()
               if recipient in (aid, item['native'], item.get('runtime'))]
    if len(matches) != 1:
        raise Refused(mctx('delivery has no unique operations recipient'))
    recipient = matches[0]
    item = state['agents'][recipient]
    assignment = Assignment.read(store.manifest(recipient, item['revision']))
    text = parameters['message']
    if not isinstance(text, str) or not text:
        raise Refused(mctx('delivery message must be a nonempty string'))
    record = Record()
    delivery = secrets.token_hex(16)
    envelope = text + "\n\n" + ENVELOPE.format(delivery=delivery, scratch=assignment.scratch)
    record.prepare(delivery, binding.agent, recipient, target, text, envelope, assignment.scratch)
    return {'delivery': delivery, 'tool': 'send_message',
            'reconcile': RECONCILE.format(scratch=scratch, sender=binding.agent,
                native=state['agents'][binding.agent]['native']),
            'call': {'target': target, 'message': envelope}}


def received(scratch: Path, delivery: str, home: Path) -> dict[str, Any]:
    from codex_ticket import Phase, Refused, bound
    from codex_reconcile import settle

    binding, store = bound(scratch)
    record = Record()
    prepared = record.delivery(delivery)
    if prepared['recipient'] != binding.agent or Path(prepared['scratch']).resolve() != scratch.resolve():
        raise Refused(mctx('delivery belongs to another recipient'))
    state = store.snapshot()
    existing = state.get('deliveries', {}).get(delivery)
    if existing is not None:
        publish_receipt(record, binding.agent, delivery, existing)
        return existing
    current = state['agents'][binding.agent]
    if current['phase'] not in (Phase.RESERVED, Phase.RUNNING):
        raise Refused(mctx('delivery has no current accepted running turn'))
    current = settle(store, binding.agent, current['native'] or current.get('runtime'), home)
    if current['phase'] != Phase.RUNNING or current['native'] is None or current['turn'] is None:
        raise Refused(mctx('delivery has no current accepted running turn'))
    receipt = {'revision': current['revision'], 'thread': current['native'],
               'turn': current['turn'], 'at': time.time()}
    with store.locked() as state:
        item = state['agents'][binding.agent]
        if (item['revision'], item['native'], item['turn'], item['phase']) != (
                receipt['revision'], receipt['thread'], receipt['turn'], Phase.RUNNING):
            raise Refused(mctx('delivery execution changed before acknowledgement'))
        receipt = state.setdefault('deliveries', {}).setdefault(delivery, receipt)
    publish_receipt(record, binding.agent, delivery, receipt)
    return receipt


def publish_receipt(record: Record, agent: str, delivery: str, receipt: dict[str, Any]) -> None:
    record.append(a.Received(source='received:' + delivery, agent=agent,
        delivery=delivery, **receipt))


def reconcile_messages(store, agent: str, home: Path) -> None:
    """Join prepared envelopes to actual native call outcomes, without inferring receipt."""
    import codex_rollout
    from codex_ticket import Refused
    from codex_native_reads import native_sends

    item = store.snapshot()['agents'][agent]
    if item['native'] is None:
        return
    record = Record()
    for send in native_sends(row for turn in codex_rollout.turns(item['native'], home) for row in turn.activity):
        args = send.arguments
        text = args.get('message', '')
        found = re.search(r'Delivery id: `([0-9a-f]{32})`\.', text)
        if found is None:
            continue
        if send.at is None:
            raise ValueError(mctx('native send has no valid occurrence time'))
        delivery = found[1]
        prepared = record.delivery(delivery)
        if (prepared['sender'], prepared['target'], prepared['envelope']) != (agent, args['target'], text):
            raise Refused(mctx('native send does not match its complete prepared envelope'))
        previous = [e for e in record.events([agent]) if isinstance(e, a.Message) and e.delivery == delivery]
        if previous and previous[0].call != send.call:
            raise Refused(mctx('delivery id already belongs to another native send'))
        record.append(a.Message(source='message:' + delivery, at=send.at, agent=agent,
            recipient=prepared['recipient'], text=prepared['text'],
            outcome=a.Outcome.ACCEPTED if send.accepted else a.Outcome.REFUSED,
            delivery=delivery, call=send.call))
