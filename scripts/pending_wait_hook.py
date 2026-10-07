"""PreToolUse hook on Bash and Monitor: denies a subagent's foreground Bash
call whose `timeout` is over `TIMEOUT_BOUND` ms, and a timed wait whose text
names, by agent id, an agent pending to the caller, as
`profile_runs.py --pending` gives the agents pending to a run.

The bound applies only where the hook input gives an agent id. A call with
`run_in_background` true, or with no `timeout`, is allowed. Where
`run_in_background` is not a bool, or `timeout` is not a number, the hook
allows the call past the bound and says why on stderr. A call denied for its
timeout is not checked for a pending agent.

Where the hook cannot tell the caller, or its check fails on its own error,
it allows the call and says why on stderr, so it can fail to deny a wait but
never denies one wrongly. A hook input inside a subagent gives the
subagent's agent id, and one that gives none is main's where the main
transcript holds the call."""

import json
import sys
from pathlib import Path
from typing import Any

from hook_entry import run_hook

HOOK = "pending_wait_hook"
TIMEOUT_BOUND = 240000


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def deny_pending(agents: list[str]) -> None:
    from controlled_markdown import mctx

    deny(mctx(
        "Blocked: this call waits on {agents}, which you launched and which "
        "has not reported since its launch or its last resume, by you or by "
        "another agent, so end your turn now, and the harness re-invokes you "
        "when it reports."
    ).format(agents=", ".join(agents)))


def over_bound(hook: dict[str, Any]) -> bool:
    """Deny the subagent's foreground Bash call `hook` gives where its
    `timeout` is over `TIMEOUT_BOUND`, and say whether it did."""
    from controlled_markdown import mctx

    inp = hook["tool_input"]
    if hook["tool_name"] != "Bash" or not hook.get("agent_id"):
        return False
    background = inp.get("run_in_background", False)
    timeout = inp.get("timeout")
    if not isinstance(background, bool):
        print(f"{HOOK}: allowed past the bound: `run_in_background` is "
              f"{background!r}, not a bool", file=sys.stderr)
        return False
    if background or timeout is None:
        return False
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        print(f"{HOOK}: allowed past the bound: `timeout` is {timeout!r}, "
              "not a number", file=sys.stderr)
        return False
    if timeout <= TIMEOUT_BOUND:
        return False
    deny(mctx(
        "Blocked: this foreground Bash call has a timeout of {timeout} ms, "
        "over the bound of {bound} ms, whatever timeout your documents give. "
        "Run the same call again with a timeout of at most {bound} ms. Where "
        "the command outlasts it, the harness moves the command to the "
        "background, and you wait on it as your documents give."
    ).format(timeout=timeout, bound=TIMEOUT_BOUND))
    return True


def check(hook: dict[str, Any]) -> None:
    """Deny the call `hook` gives where it is over the bound or waits on an
    agent pending to its caller."""
    from agent_launches import pending_agents
    from command_labels import runs_sleep
    from ticket_log import AGENT_ID
    from run_reads import blocks, session_agents, session_of
    from transcripts import main_transcript, read_entries

    if over_bound(hook):
        return
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
        deny_pending(waited)


def main() -> int:
    return run_hook(HOOK, "allowed: the check failed", check)


if __name__ == "__main__":
    sys.exit(main())
