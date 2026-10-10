"""PreToolUse hook on Bash and Monitor: denies a subagent's foreground Bash
call whose `timeout` is over `FOREGROUND_MS` ms, and a timed wait whose text
names, by agent id, an agent pending to the caller, as
`profile_runs.py --pending` gives the agents pending to a run.

The bound enforces the command notes' line on a foreground call's timeout.
Only the subagent definitions under `.claude/agents/` hold that line, so the
main session's calls are outside the bound. A Monitor call or a background Bash call holds no turn
while the prompt cache can lapse, so neither is bound.

Where the hook cannot tell the caller, it allows the call and says why on
stderr, so it can fail to deny a wait but never denies one wrongly. A call
whose input gives no agent id (`run_reads.caller_id`) is the main session's
only where the main transcript holds it."""

import re
import sys
from typing import Any

from hook_entry import run_pre_tool_use
from operations.constants import FOREGROUND_MS

HOOK = "pending_wait_hook"


def pending_reason(agents: list[str]) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: this call waits on {agents}, which you launched and which "
        "has not reported since its launch or its last resume, by you or by "
        "another agent, so end your turn now, and the harness re-invokes you "
        "when it reports."
    ).format(agents=", ".join(agents))


def over_bound(tool: str, inp: dict[str, Any], subagent: bool) -> str | None:
    """The reason to deny the call of `tool` with input `inp` where it is a
    subagent's foreground Bash call whose `timeout` is over `FOREGROUND_MS`,
    and None for any other call."""
    if tool != "Bash" or not subagent:
        return None
    background = inp.get("run_in_background", False)
    timeout = inp.get("timeout")
    if not isinstance(background, bool):
        print(f"{HOOK}: allowed past the bound: `run_in_background` is "
              f"{background!r}, not a bool", file=sys.stderr)
        return None
    if background or timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, int | float):
        print(f"{HOOK}: allowed past the bound: `timeout` is {timeout!r}, "
              "not a number", file=sys.stderr)
        return None
    if timeout <= FOREGROUND_MS:
        return None
    return bound_reason(str(timeout))


def bound_reason(timeout: str) -> str:
    """The reason the hook gives where a call's timeout, `timeout`, is over
    `FOREGROUND_MS`."""
    from controlled_markdown import mctx

    return mctx(
        "Blocked: this foreground Bash call has a timeout of {timeout} ms, "
        "over the bound of {bound} ms, whatever timeout your documents give. "
        "Run the same call again with a timeout of at most {bound} ms. Where "
        "the command outlasts it, the harness moves the command to the "
        "background, and you wait on it as your documents give."
    ).format(timeout=timeout, bound=FOREGROUND_MS)


def bound_denied(result: str) -> bool:
    """Whether `result`, a call's result, holds the reason `bound_reason`
    gives, with any timeout."""
    hole = "\0"
    parts = bound_reason(hole).split(hole)
    return re.search(r"\d+(?:\.\d+)?".join(map(re.escape, parts)), result) is not None


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the call `hook` gives where it is over the bound
    or waits on an agent pending to its caller, and None otherwise."""
    from agent_launches import pending_agents
    from command_labels import runs_sleep
    from ticket_log import AGENT_ID
    from run_reads import blocks, caller_id, caller_transcript
    from transcripts import is_subagent, read_entries

    tool, inp = hook["tool_name"], hook["tool_input"]
    if (bound := over_bound(tool, inp, caller_id(hook) is not None)) is not None:
        return bound
    if tool == "Bash":
        text = inp["command"]
        if not runs_sleep(text):
            return None
    elif tool == "Monitor":
        text = f"{inp['command']}\n{inp['description']}"
    else:
        raise ValueError(f"the hook is registered on Bash and Monitor, and "
                         f"the input gives tool `{tool}`")
    named = set(AGENT_ID.findall(text))
    if not named:
        return None
    path = caller_transcript(hook)
    if not is_subagent(path):
        call = hook["tool_use_id"]
        if not any(b.get("id") == call for e in read_entries(path)
                   for b in blocks(e, "tool_use")):
            print(f"{HOOK}: allowed: the hook input gives no agent id, and the "
                  f"main transcript {path} does not hold call {call}, so the "
                  "caller is unknown", file=sys.stderr)
            return None
    undecided: list[str] = []
    waited = [a for a in pending_agents(path, undecided) if a in named]
    for line in undecided:
        print(f"{HOOK}: undecided: {line}", file=sys.stderr)
    return pending_reason(waited) if waited else None


def main() -> int:
    from reader_commits import reader_update

    return run_pre_tool_use(HOOK, check, reader_update)


if __name__ == "__main__":
    sys.exit(main())
