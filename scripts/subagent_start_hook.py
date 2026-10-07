"""SubagentStart hook: gives each subagent, in its context at its start, its
own agent id, the `agent_id` of the hook input.

The hook never stops a launch. Where the input is not a `SubagentStart`
input, or gives no `agent_id`, or an `agent_id` that is not of the form a
ticket's log line takes, the hook prints nothing, says why on stderr, and
exits 0."""

import json
import sys
from typing import Any

from hook_entry import run_hook

HOOK = "subagent_start_hook"


def context(hook: dict[str, Any]) -> str:
    """The text the subagent that `hook` starts gets in its context."""
    from controlled_markdown import mctx
    from ticket_log import AGENT_ID

    event = hook.get("hook_event_name")
    if event != "SubagentStart":
        raise ValueError(f"the hook is registered on SubagentStart, and the "
                         f"input gives event `{event}`")
    aid = hook.get("agent_id")
    if not isinstance(aid, str) or not AGENT_ID.fullmatch(aid):
        raise ValueError(f"the input gives agent id `{aid}`, which is not of "
                         f"the form {AGENT_ID.pattern}")
    return mctx("Your agent id is {aid}.").format(aid=aid)


def give(hook: dict[str, Any]) -> None:
    """Print the hook output that gives the subagent its `context`."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStart", "additionalContext": context(hook)}}))


def main() -> int:
    return run_hook(HOOK, "gave no agent id", give)


if __name__ == "__main__":
    sys.exit(main())
