"""PreToolUse hook: runs, as one command, the checks of the hooks that
`.claude/settings.json` registers on one matcher and that can deny, so the
caller gets the reason of each check that denies, in the order of the
list, and a check that denies is recorded only when its reason reaches the
caller (`hook_entry.run_pre_tool_use`). The argument names the matcher:
`handback` for `SubagentHandback`, whose checks are those of
`operator_stop_hook`, `checklist_walk_hook` and `report_file_hook`, and
`agent` for `Agent`, whose checks are those of `context_bound_hook` and
`printed_launch_hook`, with the update of `context_bound_hook`. Each check
keeps its own guard against denying one event twice."""

import sys

from hook_entry import run_pre_tool_use

HOOK = "joined_hooks"
HANDBACK = "handback"
AGENT = "agent"


def main() -> int:
    match sys.argv[1:]:
        case [arg] if arg == HANDBACK:
            import checklist_walk_hook
            import operator_stop_hook
            import report_file_hook

            return run_pre_tool_use(HOOK, [operator_stop_hook.check, checklist_walk_hook.check,
                                           report_file_hook.check])
        case [arg] if arg == AGENT:
            import context_bound_hook
            import printed_launch_hook
            from reader_delivery import reader_update

            return run_pre_tool_use(HOOK, [context_bound_hook.check, printed_launch_hook.check],
                                    reader_update)
        case args:
            raise SystemExit(f"{HOOK}: usage: joined_hooks.py {HANDBACK}|{AGENT}, "
                             f"given `{' '.join(args)}`")


if __name__ == "__main__":
    sys.exit(main())
