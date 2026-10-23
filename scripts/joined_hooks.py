"""PreToolUse hook: runs, as one command, the checks of the hooks that
`.claude/settings.json` registers on one matcher and that can deny, so the
caller gets the reason of each check that denies, in the order of the
list, and a check that denies is recorded only when its reason reaches the
caller (`hook_entry.run_pre_tool_use`). The argument names the matcher:
`handback` for `SubagentHandback`, whose checks are those of
`operator_stop_hook`, `codex_relay_hook`, `checklist_walk_hook` and
`report_file_hook`, `send`
for `SendMessage`, whose check is that of `printed_send_hook`, and `agent`
for `Agent`, whose checks are those of `context_bound_hook` and
`printed_launch_hook`, and `bash` for `Bash|Monitor`, including the project-agent delete check.
Each runs with the reader update (`reader_delivery.reader_update`). Checks that record a denial keep their own guards against
denying one event twice."""

import sys
from typing import Any

from hook_entry import run_pre_tool_use

HOOK = "joined_hooks"
HANDBACK = "handback"
SEND = "send"
AGENT = "agent"
BASH = "bash"


def checklist_bash(hook: dict[str, Any]) -> str | None:
    if hook.get("tool_name") != "Bash":
        return None
    command = str((hook.get("tool_input") or {}).get("command", ""))
    if "scripts/step.py" not in command:
        return None
    import checklist_walk_hook

    return checklist_walk_hook.bash_check(hook)


def main() -> int:
    match sys.argv[1:]:
        case [arg] if arg == HANDBACK:
            import checklist_walk_hook
            import codex_relay_hook
            import operator_stop_hook
            import report_file_hook
            from reader_delivery import reader_update

            return run_pre_tool_use(HOOK, [operator_stop_hook.check, codex_relay_hook.check,
                                           checklist_walk_hook.check, report_file_hook.check],
                                    reader_update)
        case [arg] if arg == SEND:
            import printed_send_hook
            from reader_delivery import reader_update

            return run_pre_tool_use(HOOK, [printed_send_hook.check], reader_update)
        case [arg] if arg == AGENT:
            import context_bound_hook
            import printed_launch_hook
            from reader_delivery import reader_update

            return run_pre_tool_use(HOOK, [context_bound_hook.check, printed_launch_hook.check],
                                    reader_update)
        case [arg] if arg == BASH:
            import codex_bash_hook
            import detached_bash_hook
            import delete_bash_hook
            import pending_wait_hook
            from reader_delivery import reader_update

            return run_pre_tool_use(HOOK, [pending_wait_hook.check, codex_bash_hook.check,
                                           detached_bash_hook.check, checklist_bash, delete_bash_hook.check],
                                    reader_update)
        case args:
            raise SystemExit(f"{HOOK}: usage: joined_hooks.py {HANDBACK}|{SEND}|{AGENT}|{BASH}, "
                             f"given `{' '.join(args)}`")


if __name__ == "__main__":
    sys.exit(main())
