"""SubagentStart hook: gives each subagent, in its context at its start, its
own agent id, the `agent_id` of the hook input, and after it the start
diff of its documents, where it has no record yet and gets one, as the
module docstring of `scripts/reader_commits.py` gives the start diff and
the record (`reader_commits.start_agent`).

Where the input is not a `SubagentStart` input, or gives no `agent_id`, or
an `agent_id` that is not of the form a ticket's log line takes, the hook
gives no agent id. Of these, an `agent_id` of another form still gets its
record and its start diff."""

import json
import sys
from typing import Any

from hook_entry import not_registered, run_hook, run_part

HOOK = "subagent_start_hook"
NO_AGENT_ID = "gave no agent id"


def started(hook: dict[str, Any]) -> str:
    """The `agent_id` of the `SubagentStart` input `hook`. Any other event,
    and an input that gives no `agent_id`, are faults: the record of such
    an input would be the main session's (`run_reads.caller_id`)."""
    event = hook.get("hook_event_name")
    if event != "SubagentStart":
        raise not_registered("SubagentStart", "event", event)
    aid = hook.get("agent_id")
    if not isinstance(aid, str) or not aid:
        raise ValueError(f"the input gives agent id `{aid}`")
    return aid


def context(aid: str) -> str:
    """The agent id line the subagent `aid` gets in its context."""
    from controlled_markdown import mctx
    from ticket_log import AGENT_ID

    if not AGENT_ID.fullmatch(aid):
        raise ValueError(f"the input gives agent id `{aid}`, which is not of "
                         f"the form {AGENT_ID.pattern}")
    return mctx("Your agent id is {aid}.").format(aid=aid)


def give(line: str | None, diff: str | None) -> None:
    """Print the hook output that gives the subagent its agent id `line`
    and its start diff `diff`, where it gets either."""
    text = "\n\n".join(part for part in (line, diff) if part is not None)
    if text:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SubagentStart", "additionalContext": text}}), flush=True)


def act(hook: dict[str, Any]) -> None:
    from reader_commits import RECORD_FAILED, start_agent

    aid = started(hook)
    line = run_part(HOOK, NO_AGENT_ID, lambda: context(aid))
    printed = False

    def record() -> None:
        nonlocal printed
        with start_agent(hook) as diff:
            give(line, diff)
            printed = True

    run_part(HOOK, RECORD_FAILED, record)
    if not printed:
        give(line, None)


def main() -> int:
    return run_hook(HOOK, NO_AGENT_ID, act)


if __name__ == "__main__":
    sys.exit(main())
