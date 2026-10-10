"""PreToolUse hook on Agent: denies the Agent call of an operator subagent
that is not the launch `operate.py next` last printed to it, other than the
launch of a reply-only agent (`context_bound_hook.reply_only`).

The printed launch is read from the result of the last call of `next` in
the caller's own transcript (`printing.printed_launch`). Where that result
gives no whole launch, or a parameter of the call differs from the printed
one, the denial gives what the operator calls instead. Where the hook
cannot tell the caller's agent type, it allows the call and says why on
stderr."""

import sys
from collections.abc import Iterable
from contextlib import nullcontext
from typing import Any

from context_bound_hook import OPERATOR, reply_only
from hook_entry import run_pre_tool_use

HOOK = "printed_launch_hook"


def differing(printed: dict[str, str], inp: dict[str, Any]) -> list[tuple[str, str | None, str | None]]:
    """Each parameter that differs between the printed launch `printed` and
    the call input `inp`, with its printed and its given value, None where
    one gives none, in the printed order, then each other parameter of the
    call by name."""
    from operations.printing import parameter

    names = [*printed, *sorted(k for k in inp if k not in printed)]
    out: list[tuple[str, str | None, str | None]] = []
    for name in names:
        want = printed.get(name)
        got = parameter(inp[name]) if name in inp else None
        if want != got:
            out.append((name, want, got))
    return out


def last_next(entries: Iterable[dict[str, Any]], agent: str) -> str | None:
    """The result of the last call of `next` for the operator `agent` among
    `entries`, read last first, or None where none has a result."""
    from operations.command_words import is_next
    from run_reads import blocks, result_text

    results: dict[str, str] = {}
    for e in entries:
        if e.get("type") == "user":
            for b in blocks(e, "tool_result"):
                results.setdefault(b.get("tool_use_id", ""),
                                   result_text(b, e.get("toolUseResult")))
        elif e.get("type") == "assistant":
            for b in reversed(blocks(e, "tool_use")):
                command = str((b.get("input") or {}).get("command", ""))
                if (b.get("name") == "Bash" and is_next(command, agent)
                        and b.get("id", "") in results):
                    return results[b["id"]]
    return None


def no_launch_reason(command: str) -> str:
    from controlled_markdown import mctx

    return mctx(
        "Blocked: the last result of `{command}` gives no whole launch. Make "
        "only the launch that `next` prints, and run `next` with no pipe."
    ).format(command=command)


def differ_reason(command: str, diffs: list[tuple[str, str | None, str | None]]) -> str:
    from controlled_markdown import mctx

    head = mctx(
        "Blocked: this Agent call differs from the launch the last result of "
        "`{command}` prints. Make the call again with each parameter as "
        "printed:"
    ).format(command=command)
    none = mctx("none")
    lines = [f"- `{name}`: printed `{none if want is None else want}`, given "
             f"`{none if got is None else got}`" for name, want, got in diffs]
    return "\n".join([head, *lines])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Agent call `hook` gives where its caller is an
    operator and the call is not the launch `next` last printed to it, and
    None otherwise."""
    from operations.command_words import next_command
    from operations.printing import printed_launch
    from run_reads import UNKNOWN_TYPE, agent_type, caller_id, caller_transcript
    from transcripts import entries_back

    tool, inp = hook["tool_name"], hook["tool_input"]
    if tool != "Agent":
        raise ValueError(f"the hook is registered on Agent, and the input "
                         f"gives tool `{tool}`")
    if reply_only(inp):
        return None
    path = caller_transcript(hook)
    kind = agent_type(path)
    if kind is None:
        print(f"{HOOK}: allowed: {UNKNOWN_TYPE.format(path=path)}",
              file=sys.stderr)
        return None
    agent = caller_id(hook)
    if kind != OPERATOR or agent is None:
        return None
    command = next_command(agent)
    result = last_next(entries_back(path), agent)
    printed = None if result is None else printed_launch(result)
    if printed is None:
        return no_launch_reason(command)
    diffs = differing(printed, inp)
    return differ_reason(command, diffs) if diffs else None


def main() -> int:
    return run_pre_tool_use(HOOK, check, lambda hook: nullcontext(None))


if __name__ == "__main__":
    sys.exit(main())
