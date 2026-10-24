"""PreToolUse, PostToolUse, PostToolUseFailure and UserPromptSubmit hook:
gives the caller the update of its documents
(`reader_delivery.reader_update`), as a PreToolUse hook with the argument
`pre-tool-use`, and with no argument on the other events.
`scripts/reader_update_hook.sh` runs it, where the update may give
something."""

import sys
from contextlib import contextmanager

from hook_entry import run_context, run_pre_tool_use

HOOK = "reader_update_hook"
PRE_TOOL_USE = "pre-tool-use"


def main() -> int:
    from reader_delivery import reader_update

    from controlled_markdown import mctx

    @contextmanager
    def updated(data):
        from attempt_hook import tool
        from hook_entry import run_part
        run_part(HOOK, "failed to record the completed action", lambda: tool(data))
        with reader_update(data) as update:
            yield update

    match sys.argv[1:]:
        case []:
            return run_context(HOOK, updated)
        case [arg] if arg == PRE_TOOL_USE:
            return run_pre_tool_use(HOOK, [], reader_update)
        case args:
            raise SystemExit(mctx("{hook}: takes no argument or `{pre}`, and is "
                                  "given `{given}`").format(
                hook=HOOK, pre=PRE_TOOL_USE, given=" ".join(args)))


if __name__ == "__main__":
    sys.exit(main())
