"""Stop and SubagentHandback check for a Codex launcher. It blocks while
a relay command (`RELAYED`) runs in the background, or its output or an
agent message reached the launcher after its last Codex start. Handback
deliveries do not block. Read faults allow the stop or handback with a
reason on stderr. Each state is denied at most once, recorded by its last
message entry key, relay result or Codex launch call id."""

import sys
from typing import Any

from controlled_markdown import mctx
from hook_entry import joined, not_registered

HOOK = "codex_relay_hook"
DENIALS = "codex-relay-denials"
RELAYED = frozenset({("operate.py", "review"), ("trial_agent.py", "run")})
RUNNING = mctx(
    "- Blocked: `{command}` still runs in the background, and Codex's work waits on its "
    "output. Before any other step this denial gives, wait for its completion "
    "notification as [waiting-on-commands](prompts/agents/notes/commands.md#waiting-on-commands) "
    "gives, and do not read its output file in the wait. Then read that file in a "
    "separate Bash call, resume Codex once with that output and with each other step "
    "this denial gives, and hand back Codex's updated reply.\n"
    "    + xref: prompts/agents/notes/commands.md#waiting-on-commands")
UNPASSED = mctx(
    "- Blocked: the output of `{command}` reached you after your last Codex launch "
    "command started, so Codex has not received it. Resume Codex with that output "
    "and with each other step this denial gives, then hand back Codex's updated reply.")
# Ticket 11-3830, Motivation: launchers a64d547fe026161ae and
# a70f21f56b0ff9aec dropped messages after handback with the resume rule
# of prompts/agents/codex-launcher.md#codex-launcher in their context.
MESSAGE = mctx(
    "- Blocked: a message from {sender} reached you after your last Codex launch "
    "command started, so Codex has not received it. Resume Codex with each such "
    "message as it stands, with its sender's agent id, and each other result this "
    "denial asks you to pass, as [Codex launcher]"
    "(prompts/agents/codex-launcher.md#codex-launcher) gives. Then hand back "
    "Codex's updated reply.\n"
    "    + xref: prompts/agents/codex-launcher.md#codex-launcher")


def check(hook: dict[str, Any]) -> str | None:
    """The reason to block the stop or handback `hook` gives for relay
    output or messages Codex still waits on, once per state, and None
    otherwise or on a read fault."""
    tool = hook.get("tool_name")
    if tool is not None and tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    try:
        from agent_reports import handed_back
        from codex_reads import launches
        from command_labels import programs
        from entry_reads import entries_forward
        from operations.roles import CODEX_LAUNCHER
        from printed_launch_hook import first_at
        from run_backgrounds import note_told
        from run_reads import (agent_messages, agent_type, blocks, caller_id, caller_transcript,
                               output_file, tool_results)
        from transcript_entries import epoch

        path = caller_transcript(hook)
        kind = agent_type(path)
        if kind is None:
            raise ValueError(f"the agent type at {path} is unknown")
        if kind != CODEX_LAUNCHER:
            return None
        commands: dict[str, str] = {}
        results: dict[str, tuple[bool, float]] = {}
        told: dict[str, float] = {}
        messages: list[tuple[float, str, str]] = []
        started = float("-inf")
        last = ""
        enrolled = False
        for entry in entries_forward(path):
            note_told(told, entry)
            for sender, text in agent_messages(entry):
                if handed_back(text) is None:
                    messages.append((epoch(entry["timestamp"]), entry["uuid"], sender))
            for call, _, scratch, _ in launches(entry):
                from codex_ticket import Binding
                enrolled = Binding.read(scratch) is not None
                started = epoch(entry["timestamp"])
                last = call
            if entry.get("type") == "assistant":
                for block in blocks(entry, "tool_use"):
                    if block["name"] == "Bash":
                        command = block["input"]["command"]
                        if any(args and (program, args[0]) in RELAYED
                               and (not enrolled or (program, args[0]) != ("operate.py", "review"))
                               for program, args in programs(command)):
                            commands[block["id"]] = command
            for call, block, _ in tool_results(entry):
                if call in commands:
                    results[call] = (output_file(block) is not None, epoch(entry["timestamp"]))
                    last = call
        reasons: list[str] = []
        for call, (background, at) in results.items():
            reached = told.get(call) if background else at
            if background and reached is None:
                reason = RUNNING
            elif reached is not None and reached > started:
                reason = UNPASSED
            else:
                continue
            reasons.append(reason.format(command=commands[call]))
            break
        pending = [(key, sender) for at, key, sender in messages if at > started]
        if pending:
            last, sender = pending[-1]
            reasons.append(MESSAGE.format(sender=sender))
        if not reasons:
            return None
        agent = caller_id(hook)
        if agent is None:
            raise ValueError("the launcher agent id is unknown")
        if not first_at(hook, DENIALS, agent, last):
            print(f"{HOOK}: allowed: a stop or handback was denied at {last}, "
                  "and no new state has followed", file=sys.stderr)
            return None
        return joined(reasons)
    except Exception as error:
        why = " ".join(str(error).splitlines())
        print(f"{HOOK}: allowed: cannot read your relay commands: {why}", file=sys.stderr)
        return None
