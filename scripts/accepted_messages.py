"""Whether a message to a run that the harness accepted waits for
delivery."""

from pathlib import Path

from agent_deliveries import DELIVERED, Delivery, delivery, report_delivered, succeeded
from agent_launches import callees
from run_reads import blocks, read_meta, run_sessions
from session_changes import changed_since
from transcripts import agent_id
from transcript_entries import epoch, read_entries


def accepted_after(path: Path, since: float, undecided: list[str]) -> bool:
    """Whether a transcript of the sessions of the run at `path` holds a
    message to that run that the harness accepted after `since`, as
    `operate.py --help next` gives one."""
    names = {agent_id(path)}
    if (name := (read_meta(path) or {}).get("name")):
        names.add(str(name))
    mine = callees(path, undecided)
    for p in changed_since(run_sessions(path), since):
        hands_back = agent_id(p) in mine
        words = names | {d.value for d in Delivery}
        if hands_back:
            words |= {"SubagentHandback", DELIVERED}
        entries = [e for e in read_entries(p, naming=words) if e.get("timestamp")]
        results = {b.get("tool_use_id", ""): (r, epoch(e["timestamp"])) for e in entries
                   if e.get("type") == "user" and isinstance(r := e.get("toolUseResult"), dict)
                   for b in blocks(e, "tool_result")}
        for e in entries:
            if e.get("type") != "assistant":
                continue
            for b in blocks(e, "tool_use"):
                r, t = results.get(b.get("id", ""), ({}, 0.0))
                if t <= since or not succeeded(r):
                    continue
                if b.get("name") == "SubagentHandback" and hands_back and report_delivered(r):
                    return True
                if (b.get("name") == "SendMessage"
                        and str((b.get("input") or {}).get("to", "")) in names
                        and delivery(r) is not None):
                    return True
    return False
