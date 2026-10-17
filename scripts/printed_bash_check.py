"""The check `pending_wait_hook` runs on the Bash call of an agent of a type
of `context_bound_hook.ACTIONS`, which makes only the calls its command
prints; the command runs each Bash step itself. It denies a call that is not
that command alone (`command_words.only_command`), and a call of that command
where the last result of that command prints a call of any tool, and the
transcript holds, after that result, no call of that tool and no message or notification that reached
the caller (`run_reads.is_prompt`). A call another hook denied counts as
made: it stands in the transcript.

Each denial is recorded with the id of the call of the command whose result
it reads, in a file named by the caller's agent id under `DENIALS` of its
session directory, and no call is denied again while that call is still
the last: a fault in the check then denies at most one call per result.
The check allows the call of an agent of any other type, and of an agent
whose type it cannot tell, which `printed_launch_hook.operator_next` says
on stderr."""

import sys
from typing import Any

from operations.state import Tool

HOOK = "printed_bash_check"
DENIALS = "printed-call-denials"


def printed_call(result: str) -> tuple[Tool, str] | None:
    """The tool and the text of the call `result`, a result of the command,
    prints, or None where it prints no call."""
    from operations.printing import PROMPT, launch_text, printed_launch, printed_send, send_text

    launch = printed_launch(result)
    if launch is not None:
        fields = {k: v for k, v in launch.items() if k != PROMPT}
        return Tool.AGENT, launch_text(fields, launch[PROMPT])
    send = printed_send(result)
    return None if send is None else (Tool.SEND_MESSAGE, send_text(*send))


def made_since(entries: list[dict[str, Any]], tool: Tool, current: str) -> bool:
    """Whether `entries`, the transcript after a result of the command,
    holds a call of `tool` other than the call `current` the hook holds,
    or a message or notification that reached the caller."""
    from run_reads import blocks, is_prompt

    return any(is_prompt(e) or any(b.get("name") == tool.value and b.get("id") != current
                                   for b in blocks(e, "tool_use"))
               for e in entries)


def after_call(path: Any, call: str) -> list[dict[str, Any]]:
    """The entries of the transcript at `path` after the result of `call`,
    in their order."""
    from run_reads import tool_results
    from transcript_entries import entries_back

    out: list[dict[str, Any]] = []
    for e in entries_back(path):
        if any(c == call for c, _, _ in tool_results(e)):
            return out[::-1]
        out.append(e)
    raise ValueError(f"the transcript {path} holds no result of call {call}")


def with_call(reason: str, printed: str) -> str:
    from controlled_markdown import mctx

    return "\n".join([reason, mctx("Make that call:"), printed])


def off_script_reason(command: str, printed: str | None) -> str:
    from controlled_markdown import mctx

    if printed is None:
        return "\n".join([
            mctx("Blocked: this Bash call is not `{command}`, and the last result of "
                 "`{command}` prints no call."),
            mctx("Run `{command}`, and make each call it prints."),
        ]).format(command=command)
    return with_call(
        mctx("Blocked: this Bash call is not `{command}`, and the last result of "
             "`{command}` prints a call of another tool.").format(command=command), printed)


def skip_reason(command: str, printed: str) -> str:
    from controlled_markdown import mctx

    return with_call(
        mctx("Blocked: this Bash call runs `{command}` again, and you have not made the "
             "call its last result prints.").format(command=command), printed)


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Bash call `hook` gives where the module
    docstring has it denied, and None otherwise."""
    from operations.command_words import only_command
    from printed_launch_hook import first_at, operator_next
    from run_reads import caller_transcript

    caller = operator_next(hook, HOOK)
    if caller is None:
        return None
    found = caller.found
    printed = None if found is None else printed_call(found[1])
    text = str(hook["tool_input"]["command"])
    if only_command(text, caller.agent, caller.action):
        if found is None or printed is None:
            return None
        tool, call_text = printed
        if made_since(after_call(caller_transcript(hook), found[0]), tool,
                      hook["tool_use_id"]):
            return None
        reason = skip_reason(caller.command, call_text)
    else:
        reason = off_script_reason(caller.command, None if printed is None else printed[1])
    last = "" if found is None else found[0]
    if not first_at(hook, DENIALS, caller.agent, last):
        print(f"{HOOK}: allowed: a call was denied at call {last} of `{caller.command}`, "
              "and the caller made no call of it since", file=sys.stderr)
        return None
    return reason

