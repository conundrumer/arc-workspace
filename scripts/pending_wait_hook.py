"""PreToolUse hook on Bash and Monitor: denies a subagent's foreground Bash
call whose `timeout` is over `FOREGROUND_MS` ms, a Bash call that
`printed_bash_check` denies, and a timed wait whose text names, by agent
id, an agent pending to the caller, as `profile_runs.py --pending` gives
the agents pending to a run. The check of `printed_bash_check` runs in this
process, so that no Bash call starts a process of its own for it.
It also denies a subagent's foreground Bash call of `scripts/operate.py`
with an action of `command_words.Action` whose `timeout` is not set or is
under `FOREGROUND_MS`, since such a call can block for up to `LIMIT_SECONDS`.
That denial is recorded once per identical call input; read faults allow
that call with a reason on stderr.

The bound enforces the command notes' line on a foreground call's timeout.
Only the subagent definitions under `.claude/agents/` hold that line, so the
main session's calls are outside the bound. A Monitor call or a background Bash call holds no turn
while the prompt cache can lapse, so neither is bound.

Where the hook cannot tell the caller, it allows the call and says why on
stderr, so it can fail to deny a wait but never denies one wrongly. A call
whose input gives no agent id (`run_reads.caller_id`) is the main session's
only where the main transcript holds it."""

import sys
from typing import Any

from hook_entry import not_registered, run_pre_tool_use
from operations.constants import FOREGROUND_MS
from wait_bound import bound_reason, short_reason

HOOK = "pending_wait_hook"


def pending_reason(agents: list[str], caller: str | None) -> str:
    """The denial of a wait on `agents`, which gives a subagent `caller` the
    start of its keep-alive timer, and the main session, `caller` None, no
    timer, since its documents hold none."""
    from controlled_markdown import mctx

    blocked = mctx(
        "Blocked: this call waits on {agents}, which you launched and which "
        "has not reported since its launch or its last resume, so end your "
        "turn now: the harness re-invokes you when it reports."
    ).format(agents=", ".join(agents))
    if caller is None:
        return blocked
    return blocked + "\n" + mctx(
        "Before you end your turn, start your keep-alive timer, as "
        "[Background agents](prompts/agents/notes/commands.md#background-agents) "
        "gives, with `{caller}` as `<agent id>`."
    ).format(caller=caller)


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


def under_bound(tool: str, inp: dict[str, Any], subagent: bool,
                hook: dict[str, Any]) -> str | None:
    """The denial for an operation with too short a foreground timeout,
    recorded with caller context `hook`, or None on a read fault or retry."""
    if tool != "Bash" or not subagent:
        return None
    try:
        import hashlib
        import json

        from command_labels import programs
        from operations.command_words import Action
        from printed_launch_hook import first_at
        from run_reads import caller_id

        background = inp.get("run_in_background", False)
        if not isinstance(background, bool):
            raise ValueError(f"`run_in_background` is {background!r}, not a bool")
        if background:
            return None
        timeout = inp.get("timeout")
        if timeout is not None and (isinstance(timeout, bool)
                                    or not isinstance(timeout, int | float)):
            raise ValueError(f"`timeout` is {timeout!r}, not a number")
        if timeout is not None and not timeout < FOREGROUND_MS:
            return None
        actions = {a.value for a in Action}
        action = next((args[0] for program, args in programs(inp["command"])
                       if program == "operate.py" and args and args[0] in actions), None)
        if action is None:
            return None
        agent = caller_id(hook)
        if agent is None:
            raise ValueError("the caller agent id is unknown")
        call = hashlib.sha256(json.dumps(inp, sort_keys=True).encode()).hexdigest()
        if not first_at(hook, "short-timeout-denials", f"{agent}-{call}", call):
            print(f"{HOOK}: allowed: this identical call was already denied "
                  "for its foreground timeout", file=sys.stderr)
            return None
        return short_reason(action, None if timeout is None else str(timeout))
    except Exception as error:
        why = " ".join(str(error).splitlines())
        print(f"{HOOK}: allowed: cannot check the lower bound: {why}", file=sys.stderr)
        return None


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the call `hook` gives for its timeout,
    where `printed_bash_check` denies it, or where it waits on an agent
    pending to its caller, and None otherwise."""
    import printed_bash_check
    from agents_pending import pending_agents
    from command_labels import runs_sleep
    from ticket_log import AGENT_ID
    from run_reads import blocks, caller_id, caller_transcript
    from transcripts import is_subagent
    from entry_reads import read_entries

    tool, inp = hook["tool_name"], hook["tool_input"]
    if (bound := over_bound(tool, inp, caller_id(hook) is not None)) is not None:
        return bound
    if (bound := under_bound(tool, inp, caller_id(hook) is not None, hook)) is not None:
        return bound
    if tool == "Bash":
        if (off_script := printed_bash_check.check(hook)) is not None:
            return off_script
        text = inp["command"]
        if not runs_sleep(text):
            return None
    elif tool == "Monitor":
        text = f"{inp['command']}\n{inp['description']}"
    else:
        raise not_registered("Bash and Monitor", "tool", tool)
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
    return pending_reason(waited, caller_id(hook)) if waited else None


def main() -> int:
    from reader_delivery import reader_update

    return run_pre_tool_use(HOOK, [check], reader_update)


if __name__ == "__main__":
    sys.exit(main())
