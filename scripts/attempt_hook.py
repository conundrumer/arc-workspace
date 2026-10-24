"""Claude lifecycle evidence from completed tool results and permitted stops."""

from controlled_markdown import mctx

import time
from pathlib import Path
from typing import Any

from attempt_record import Record
from operations import attempts as a
from operations.roles import CODEX_LAUNCHER, described

TOOLS = frozenset({'Agent', 'SendMessage', 'SubagentHandback', 'TaskStop'})


def occurrence(record: Record, source: str) -> float:
    at = record.timestamp(source)
    return time.time() if at is None else at


def tool(hook: dict[str, Any], record: Record | None = None) -> None:
    from agent_deliveries import Delivery, delivery, handback_accepted, succeeded
    from agent_reports import handed_back
    from agent_resumes import pin_id
    from run_reads import caller_id

    event = hook['hook_event_name']
    name = hook.get('tool_name')
    if event == 'UserPromptSubmit':
        notification(hook, record)
        return
    if event not in ('PostToolUse', 'PostToolUseFailure') or name not in TOOLS:
        return
    record = record or Record()
    sender = caller_id(hook) or hook['session_id']
    source = 'claude:' + sender + ':' + hook['tool_use_id']
    at = record.timestamp(source)
    if at is None:
        at = hook.get('_at', time.time())
    args = hook['tool_input']
    result = hook.get('tool_response')
    if not isinstance(result, dict):
        raise ValueError(mctx('tool response is not an object'))
    failed = event == 'PostToolUseFailure'
    if name == 'Agent':
        seat = described(args['description'])
        if seat is None or failed:
            return
        agent = result.get('agentId')
        if not isinstance(agent, str):
            raise ValueError(mctx('Agent result has no agent id'))
        record.append(a.Launched(source=source, at=at, agent=agent, parent=sender,
            seat=seat, agent_type=args['subagent_type'], transport=a.Transport.CLAUDE))
    elif name == 'SendMessage':
        recipient = result.get('resumedAgentId') or pin_id(result) or args.get('recipient') or args.get('agent_id')
        if not isinstance(recipient, str):
            raise ValueError(mctx('SendMessage has no recipient id'))
        text = args.get('message', args.get('content'))
        if not isinstance(text, str):
            raise ValueError(mctx('SendMessage input has no message text'))
        accepted = not failed and (succeeded(result) or delivery(result) is not None
                                  or bool(result.get('resumedAgentId')))
        record.append(a.Message(source=source, at=at, agent=sender, recipient=recipient,
            text=text, outcome=a.Outcome.ACCEPTED if accepted else a.Outcome.REFUSED,
            call=hook['tool_use_id'], delivery=source, handback=handed_back(text) is not None))
        previous = a.fold(record.events([recipient])).get(recipient)
        if accepted and (delivery(result) is Delivery.RESUMED or (previous is not None and previous.stopped)):
            record.append(a.Resumed(source=source + ':resume', at=at, agent=recipient, parent=sender))
    elif name == 'SubagentHandback' and not failed and handback_accepted(result):
        record.append(a.HandedBack(source=source, at=at, agent=sender, text=args['message']))
    elif name == 'TaskStop' and not failed:
        agent = result.get('agentId')
        if isinstance(agent, str) and (result.get('stopped') is True or result.get('status') in ('stopped', 'killed')):
            record.append(a.Stopped(source=source, at=at, agent=agent, text='', killed=True))


def stopped(hook: dict[str, Any], record: Record | None = None) -> None:
    agent = hook.get('agent_id')
    if not agent:
        return
    record = record or Record()
    text = hook.get('last_assistant_message')
    if not isinstance(text, str):
        from entry_reads import read_entries
        from run_reads import text_of
        path = Path(hook['agent_transcript_path'] if 'agent_transcript_path' in hook else hook['transcript_path'])
        entries = [entry for entry in read_entries(path) if entry.get('type') == 'assistant']
        if not entries:
            raise ValueError(mctx('stopped agent transcript has no assistant entry'))
        text = text_of(entries[-1].get('message', {}).get('content'))
    import hashlib
    resumes = [e.source for e in record.events([agent]) if isinstance(e, a.Resumed) and e.agent == agent]
    source = 'stop:' + agent + ':' + (resumes[-1] if resumes else '') + ':' + hashlib.sha256((str(hook.get('transcript_path')) + text).encode()).hexdigest()
    record.append(a.Stopped(source=source, at=occurrence(record, source), agent=agent, text=text))


def notification(hook: dict[str, Any], record: Record | None = None) -> None:
    from run_reads import notifications, caller_id, Status
    import hashlib
    text = hook.get('prompt')
    if not isinstance(text, str):
        return
    record = record or Record()
    owner = caller_id(hook) or hook['session_id']
    for note in notifications({'type': 'user', 'message': {'content': text}}):
        if note.status not in (Status.COMPLETED, Status.FAILED):
            continue
        for child in note.ids:
            attempt = a.fold(record.events([child])).get(child)
            if attempt is None or attempt.launch is None:
                continue
            resumes = [e for e in attempt.events if isinstance(e, a.Resumed)]
            parent = resumes[-1].parent if resumes else attempt.launch.parent
            if parent != owner:
                continue
            source = 'notification:' + child + ':' + hashlib.sha256(text.encode()).hexdigest()
            owning = a.fold(record.events([owner])).get(owner)
            prior = [e for e in owning.events if isinstance(e, a.Resumed)] if owning else []
            notification_owner = prior[-1].parent if prior else (owning.launch.parent if owning and owning.launch else None)
            record.append(a.Resumed(source=source, at=occurrence(record, source), agent=owner,
                                    parent=notification_owner))
