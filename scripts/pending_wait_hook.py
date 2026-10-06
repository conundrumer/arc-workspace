"""PreToolUse hook on Bash and Monitor, which denies a call on two checks.

The wait check, `pending_wait`, denies a timed wait whose text gives, by
agent id, an agent pending to the caller. Where it cannot tell the caller,
it allows the call.

The read check, `joined_read`, denies a Bash command that joins another
command with `;`, `&&`, `||`, `&` or a newline to a whole-file read: a
simple command named `cat` whose operands are files that exist and whose
text together is longer than the Bash tool's cap on a failed command's
output, slack included. It allows the call where the read's standard
output is piped or redirected, where an operand is not literal or refers to
no file that exists, where an option of `cat` can shorten its output, where
a relative operand follows a `cd`, `pushd` or `popd`, where a command before
the read can change the shell as the docstring of `joined_read.SHELL_CHANGERS`
gives, and where no command is joined to the read. It allows the call as well
where `shell_parse` cannot split the command line.

Where a check allows a call on a case it cannot judge, or fails on its own
error, the hook says why on stderr, so it can fail to deny a call but never
denies one wrongly."""

import importlib
import json
import sys

HOOK = "pending_wait_hook"


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason}}))


def main() -> int:
    try:
        hook = json.loads(sys.stdin.read())
    except ValueError as e:
        print(f"{HOOK}: allowed: the hook input is no JSON: {e}", file=sys.stderr)
        return 0
    for name, module in (("read", "joined_read"), ("wait", "pending_wait")):
        notes: list[str] = []
        try:
            reason = importlib.import_module(module).check(hook, notes)
        except Exception as e:
            reason = None
            notes.append(f"allowed: the {name} check failed: "
                         f"{type(e).__name__}: {e}")
        for note in notes:
            print(f"{HOOK}: {note}", file=sys.stderr)
        if reason:
            deny(reason)
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
