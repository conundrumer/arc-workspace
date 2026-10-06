"""SubagentStart hook: gives each subagent, in its context at its start, its
own agent id, the `agent_id` of the hook input.

The hook never stops a launch. Where the input is not a `SubagentStart`
input, or gives no `agent_id`, or an `agent_id` that is not of the form a
ticket's log line takes, the hook prints nothing, says why on stderr, and
exits 0."""

import json
import sys
from typing import Any

HOOK = "subagent_start_hook"


def context(hook: dict[str, Any]) -> str:
    """The text the subagent that `hook` starts gets in its context."""
    from ticket_log import AGENT_ID

    event = hook.get("hook_event_name")
    if event != "SubagentStart":
        raise ValueError(f"the hook is registered on SubagentStart, and the "
                         f"input gives event `{event}`")
    aid = hook.get("agent_id")
    if not isinstance(aid, str) or not AGENT_ID.fullmatch(aid):
        raise ValueError(f"the input gives agent id `{aid}`, which is not of "
                         f"the form {AGENT_ID.pattern}")
    return f"Your agent id is {aid}."


def main() -> int:
    try:
        text = context(json.loads(sys.stdin.read()))
    except Exception as e:
        print(f"{HOOK}: gave no agent id: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 0
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SubagentStart", "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
