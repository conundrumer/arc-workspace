"""PreToolUse, PostToolUse, PostToolUseFailure and UserPromptSubmit hook:
gives the caller the update of its documents
(`reader_delivery.reader_update`), as a PreToolUse hook with the argument
`pre-tool-use`, and with no argument on the other events.
`scripts/reader_update_hook.sh` runs it, where the update may give
something."""

import sys

from hook_entry import run_context, run_pre_tool_use

HOOK = "reader_update_hook"
PRE_TOOL_USE = "pre-tool-use"


def main() -> int:
    from reader_delivery import reader_update

    from controlled_markdown import mctx

    match sys.argv[1:]:
        case []:
            return run_context(HOOK, reader_update)
        case [arg] if arg == PRE_TOOL_USE:
            return run_pre_tool_use(HOOK, [], reader_update)
        case args:
            raise SystemExit(mctx("{hook}: takes no argument or `{pre}`, and is "
                                  "given `{given}`").format(
                hook=HOOK, pre=PRE_TOOL_USE, given=" ".join(args)))


if __name__ == "__main__":
    sys.exit(main())
