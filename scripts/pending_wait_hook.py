"""PreToolUse hook on Bash and Monitor: denies a timed wait whose text names,
by agent id, an agent pending to the caller, as `profile_runs.py --pending`
gives the agents pending to a run.

Where the hook cannot tell the caller, or its check fails on its own error,
it allows the call and says why on stderr, so it can fail to deny a wait but
never denies one wrongly. A hook input inside a subagent gives the
subagent's agent id, and one that gives none is main's where the main
transcript holds the call."""

import json
import sys
from pathlib import Path
from typing import Any

HOOK = "pending_wait_hook"


def deny(agents: list[str]) -> None:
    from controlled_markdown import mctx

    reason = mctx(
        "Blocked: this call waits on {agents}, which you launched and which "
        "has not reported since its launch or its last resume, by you or by "
        "another agent, so end your turn now, and the harness re-invokes you "
        "when it reports."
    ).format(agents=", ".join(agents))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def check(hook: dict[str, Any]) -> None:
    """Deny the call `hook` gives where it waits on an agent pending to its
    caller."""
    from agent_launches import pending_agents
    from command_labels import runs_sleep
    from file_ticket import AGENT_ID
    from run_reads import blocks, session_agents, session_of
    from transcripts import main_transcript, read_entries

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool == "Bash":
        text = inp["command"]
        if not runs_sleep(text):
            return
    elif tool == "Monitor":
        text = f"{inp['command']}\n{inp['description']}"
    else:
        raise ValueError(f"the hook is registered on Bash and Monitor, and "
                         f"the input gives tool `{tool}`")
    named = set(AGENT_ID.findall(text))
    if not named:
        return
    session = session_of(Path(hook["transcript_path"]))
    caller = hook.get("agent_id")
    if caller:
        path = session_agents(session).get(caller)
        if path is None:
            raise ValueError(f"no transcript of agent {caller} under {session}")
    else:
        path = main_transcript(session)
        call = hook["tool_use_id"]
        if not any(b.get("id") == call for e in read_entries(path)
                   for b in blocks(e, "tool_use")):
            print(f"{HOOK}: allowed: the hook input gives no agent id, and the "
                  f"main transcript {path} does not hold call {call}, so the "
                  "caller is unknown", file=sys.stderr)
            return
    undecided: list[str] = []
    waited = [a for a in pending_agents(path, undecided) if a in named]
    for line in undecided:
        print(f"{HOOK}: undecided: {line}", file=sys.stderr)
    if waited:
        deny(waited)


def main() -> int:
    try:
        check(json.loads(sys.stdin.read()))
    except Exception as e:
        print(f"{HOOK}: allowed: the check failed: {type(e).__name__}: {e}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
