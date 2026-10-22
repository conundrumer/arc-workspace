"""PreToolUse check on SubagentHandback for a Codex launcher. It denies
handback while a relay command (`RELAYED`) runs in the background, or its
output reached the launcher after its last Codex start. Read faults allow
handback with a reason on stderr. Each state is denied at most once,
recorded by its last relay result or Codex launch call id."""

import sys
from typing import Any

from controlled_markdown import mctx
from hook_entry import not_registered

HOOK = "codex_relay_hook"
DENIALS = "codex-relay-denials"
RELAYED = frozenset({("operate.py", "review"), ("trial_agent.py", "run")})
RUNNING = mctx(
    "Blocked: `{command}` still runs in the background, and Codex's work waits on its "
    "output. Before any other step this denial gives, wait for its completion "
    "notification as [waiting-on-commands](prompts/agents/notes/commands.md#waiting-on-commands) "
    "gives, and do not read its output file in the wait. Then read that file in a "
    "separate Bash call, resume Codex once with that output and with each other step "
    "this denial gives, and hand back Codex's updated reply.")
UNPASSED = mctx(
    "Blocked: the output of `{command}` reached you after your last Codex launch "
    "command started, so Codex has not received it. Resume Codex with that output "
    "and with each other step this denial gives, then hand back Codex's updated reply.")


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the handback `hook` gives for relay output Codex
    still waits on, once per state, and None otherwise or on a read fault."""
    tool = hook["tool_name"]
    if tool != "SubagentHandback":
        raise not_registered("SubagentHandback", "tool", tool)
    try:
        from codex_reads import launches
        from command_labels import programs
        from entry_reads import entries_forward
        from operations.roles import CODEX_LAUNCHER
        from printed_launch_hook import first_at
        from run_backgrounds import note_told
        from run_reads import (agent_type, blocks, caller_id, caller_transcript, output_file,
                               tool_results)
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
        started = float("-inf")
        last = ""
        enrolled = False
        for entry in entries_forward(path):
            note_told(told, entry)
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
        for call, (background, at) in results.items():
            reached = told.get(call) if background else at
            if background and reached is None:
                reason = RUNNING
            elif reached is not None and reached > started:
                reason = UNPASSED
            else:
                continue
            agent = caller_id(hook)
            if agent is None:
                raise ValueError("the launcher agent id is unknown")
            if not first_at(hook, DENIALS, agent, last):
                print(f"{HOOK}: allowed: handback was denied at call {last}, "
                      "and no relay result or Codex launch has followed", file=sys.stderr)
                return None
            return reason.format(command=commands[call])
        return None
    except Exception as error:
        why = " ".join(str(error).splitlines())
        print(f"{HOOK}: allowed: cannot read your relay commands: {why}", file=sys.stderr)
        return None
