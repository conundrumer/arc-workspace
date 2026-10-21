"""PreToolUse check on Bash: a Codex launcher delegates repository edits.

It also refuses a Bash call whose Codex launches the walk readers cannot read
(`codex_reads.work_calls`), or that holds more than one launch.

Recognize interpreter runs and common shell writes, including redirects,
against the main repository and its worktrees. This checks shell commands,
not the effects of the repository's own scripts and modules.
"""

import re
import shlex
from pathlib import Path

from hook_entry import Hook

def writes_repository(command: str, cwd: Path, main: Path) -> bool:
    """Whether `command` uses a checked write form in the repository.
    Inline Python is refused even where its effects cannot be read from
    the command; repository scripts and modules run through uv are allowed.
    A command whose quoting cannot be parsed is refused."""
    from command_labels import ASSIGNMENT, OPENERS, UV_OPTIONS, VARIABLE, WRAPPER_OPTIONS, WRAPPERS
    from operations.command_words import joined, without_heredocs

    cwd, main = cwd.resolve(), main.resolve()
    values = {"CLAUDE_PROJECT_DIR": str(cwd), "PWD": str(cwd)}

    def expand(word: str) -> str:
        return VARIABLE.sub(lambda m: values.get(m[1] or m[2], m[0]), word)

    def in_repo(word: str) -> bool:
        return (cwd / Path(expand(word)).expanduser()).resolve().is_relative_to(main)

    def edit_paths(args: list[str]) -> list[str]:
        paths: list[str] = []
        expression = False
        i = 0
        while i < len(args):
            word = args[i]
            if word in {"-e", "-f", "--expression", "--file"}:
                expression = True
                i += 2
            else:
                if word.startswith(("-e", "-f", "--expression=", "--file=")):
                    expression = True
                elif not word.startswith("-"):
                    paths.append(word)
                i += 1
        return paths if expression else paths[1:]

    def writes(words: list[str]) -> bool:
        nonlocal cwd
        words = [expand(w) for w in words]
        while words and words[0] in OPENERS:
            words.pop(0)
        while words and (assignment := ASSIGNMENT.fullmatch(words[0])):
            values[assignment[1]] = assignment[2]
            words.pop(0)
        # Keep uv run on the command so the Python exception can check it.
        while words and Path(words[0]).name in WRAPPERS - {"uv", "run"}:
            wrapper = Path(words.pop(0)).name
            while words and (words[0].startswith("-")
                             or re.fullmatch(r"\d+[smh]?", words[0])):
                option = words.pop(0)
                if option in WRAPPER_OPTIONS.get(wrapper, ()) and words:
                    words.pop(0)
            while words and ASSIGNMENT.fullmatch(words[0]):
                assignment = ASSIGNMENT.fullmatch(words.pop(0))
                assert assignment is not None
                values[assignment[1]] = assignment[2]
        clean: list[str] = []
        i = 0
        while i < len(words):
            word = words[i]
            if word and set(word) <= set("<>&") and set(word) & set("<>"):
                if i + 1 >= len(words):
                    return True
                target = words[i + 1]
                if ">" in word and not ("&" in word and (target.isdigit() or target == "-")):
                    if in_repo(target):
                        return True
                if clean and clean[-1].isdigit():
                    clean.pop()
                i += 2
            else:
                clean.append(word)
                i += 1
        if not clean:
            return False
        program, args = Path(clean[0]).name, clean[1:]
        if program == "cd" and args:
            cwd = (cwd / args[0]).resolve()
            values["PWD"] = str(cwd)
            return False
        if program == "uv" and args and args[0] == "run":
            clean = args[1:]
            while clean and clean[0].startswith("-"):
                option = clean.pop(0)
                if option in UV_OPTIONS and clean:
                    clean.pop(0)
            if clean and Path(clean[0]).name == "python":
                rest = clean[1:]
                while rest and rest[0] in ("-u", "-B"):
                    rest = rest[1:]
                if rest and (rest[0] == "-m" and len(rest) > 1
                             or not rest[0].startswith("-")
                             and (cwd / rest[0]).resolve().is_relative_to(main)
                             and "scripts" in Path(rest[0]).parts
                             and rest[0].endswith(".py")):
                    return False
            program, args = (Path(clean[0]).name, clean[1:]) if clean else ("", [])
        if re.fullmatch(r"python[\d.]*", program):
            return True
        if program in ("bash", "sh", "zsh") and "-c" in args:
            at = args.index("-c") + 1
            return at < len(args) and writes_repository(args[at], cwd, main)
        if program == "git":
            while args and args[0].startswith("-"):
                option = args.pop(0)
                if option in {"-C", "-c", "--git-dir", "--work-tree", "--namespace"} and args:
                    args.pop(0)
            return bool(args and args[0] in {
                "apply", "commit", "checkout", "reset", "add", "restore", "stash"})
        paths = [a for a in args if not a.startswith("-")]
        if program in ("sed", "perl"):
            return any(a.startswith("-i") or a.startswith("--in-place")
                       or program == "perl" and re.fullmatch(r"-[A-Za-z]*i[A-Za-z]*", a)
                       for a in args) and any(in_repo(p) for p in edit_paths(args))
        if program == "cp":
            for option in ("-t", "--target-directory"):
                if option in args:
                    at = args.index(option) + 1
                    return at < len(args) and in_repo(args[at])
            target = next((a.split("=", 1)[1] for a in args
                           if a.startswith("--target-directory=")), None)
            return in_repo(target) if target is not None else bool(paths and in_repo(paths[-1]))
        if program in {"mv", "rm", "tee", "touch", "mkdir", "rmdir", "truncate", "install"}:
            return any(in_repo(p) for p in paths)
        if program in {"patch", "apply_patch"}:
            return True
        return False

    lexer = shlex.shlex(joined(without_heredocs(command)), posix=True,
                        punctuation_chars=";&|()<>\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    words: list[str] = []
    try:
        for word in lexer:
            if word and set(word) <= set(";&|()\n"):
                if writes(words):
                    return True
                words = []
            else:
                words.append(word)
        return writes(words)
    except ValueError:
        return True


def check(hook: Hook) -> str | None:
    from operations.roles import CODEX_LAUNCHER
    from run_reads import agent_type, caller_transcript

    if hook["tool_name"] != "Bash":
        return None
    if agent_type(caller_transcript(hook)) != CODEX_LAUNCHER:
        return None
    import codex_reads
    from controlled_markdown import mctx
    from engine import checkout

    command = hook["tool_input"]["command"]
    try:
        found = codex_reads.work_calls(command)
    except ValueError as exc:
        return mctx("Blocked: the Codex call cannot be read: {error}. Write each launch "
                    "command with literal arguments and an absolute scratch directory.").format(error=exc)
    if len(found) > 1:
        return mctx("Blocked: give each Codex launch command its own Bash call.")
    cwd = Path(hook.get("cwd") or checkout.ROOT)
    if not writes_repository(command, cwd,
                             checkout.main_worktree(checkout.ROOT)):
        return None
    return mctx("Blocked: a Codex launcher gives the work to Codex through "
                "`scripts/codex_agent.py`; do no item's work yourself in Bash.")
