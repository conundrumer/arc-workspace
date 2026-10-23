"""PreToolUse check on Bash: denies a call whose command starts a process
that outlives the call (`command_words.detaches`), foreground or
background, since no notification reaches the caller when that process
ends. A Monitor call and any other Bash call give None."""

from hook_entry import Hook


def check(hook: Hook) -> str | None:
    from controlled_markdown import mctx
    from operations.command_words import detaches

    if hook["tool_name"] != "Bash" or not detaches(hook["tool_input"]["command"]):
        return None
    return mctx(
        "Blocked: this call leaves a process running after it ends, so no "
        "notification reaches you when that process ends. Run the command "
        "again with `run_in_background` and with no `&`, `nohup`, `disown` "
        "or `setsid`.")
