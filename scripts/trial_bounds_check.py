"""The check `pending_wait_hook` runs on the Bash call of a subagent that is
a doc reviewer's trial: a subagent whose first message opens with the line
`Trial bounds: <case time> <case commit>`. It denies a call that reads past
the trial's case: a transcript read other than `transcripts.py window` with
an end no later than the case time, a command that names a transcript file,
and a git read of history or of a diff at a revision other than the case
commit, or at none. The check allows the call of any other subagent.

A read through the `Read` tool, a variable or a script file that holds a
denied path passes the check, and the doc reviewer's reading of the trial's
transcript is what finds it."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOUNDS = re.compile(r"Trial bounds: (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)) "
                    r"([0-9a-f]{7,40})")
STAMP = 19
"""The length of an entry's time as `transcripts.py window` compares it,
`YYYY-MM-DDTHH:MM:SS`."""

TRANSCRIPT_PATH = re.compile(r"\.claude(?:-console)?/projects/|\.jsonl\b")

WINDOW_VALUED = frozenset({"--tool", "--project", "--kinds", "-w", "--width"})
WINDOW_FLAGS = frozenset({"--main-only"})

GIT_VALUED = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
"""The options of `git` before its subcommand that take the next word as
their value."""
HISTORY = frozenset({"log", "diff", "show", "rev-list", "status", "blame", "grep",
                     "ls-tree", "cat-file"})
REF_OPTIONS = ("--all", "--branches", "--remotes", "--glob", "--reflog")
VALUED = {
    "log": frozenset({"-n", "--max-count", "--author", "--committer", "--grep",
                      "-S", "-G", "-L", "--since", "--until"}),
    "rev-list": frozenset({"-n", "--max-count", "--author", "--committer", "--grep",
                           "--since", "--until"}),
    "show": frozenset({"-S", "-G"}),
    "diff": frozenset({"-S", "-G"}),
    "blame": frozenset({"-L"}),
    "grep": frozenset({"-e", "-f", "-A", "-B", "-C", "-m", "--max-depth"}),
}
"""By subcommand, its options that take the next word as their value. An
option not listed takes none."""
CAT_FILE_TYPES = frozenset({"blob", "tree", "commit", "tag"})


@dataclass(frozen=True)
class Bounds:
    time: str
    """The case time, as `STAMP` characters."""
    commit: str


def bounds(path: Path) -> Bounds | None:
    """The bounds the first line of the first user entry of the transcript
    at `path` gives, or None where that line gives none: the caller is no
    trial."""
    from run_reads import message_text
    from transcript_entries import entries_forward

    first = next((e for e in entries_forward(path) if e.get("type") == "user"), None)
    if first is None:
        return None
    m = BOUNDS.fullmatch(message_text(first).split("\n", 1)[0].strip())
    return Bounds(m.group(1)[:STAMP], m.group(2)) if m else None


def window_late(args: list[str], time: str) -> bool:
    """Whether the arguments `args` of `transcripts.py window` give an end
    later than `time`, or cannot be read as `window`'s arguments. The
    script compares an entry's time with the end as strings."""
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in WINDOW_VALUED:
            i += 2
            continue
        if a in WINDOW_FLAGS or any(a.startswith(f"{o}=") for o in WINDOW_VALUED):
            i += 1
            continue
        if a.startswith("-"):
            return True
        positional.append(a)
        i += 1
    return len(positional) < 3 or positional[1][:STAMP] > time


def git_subcommand(args: list[str]) -> tuple[str | None, list[str]]:
    """The subcommand of `git` with the arguments `args`, and its own
    arguments."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUED else 1
    return (args[i], args[i + 1:]) if i < len(args) else (None, [])


def at_case(word: str, commit: str) -> bool:
    """Whether `word` is the case commit `commit`, or `<commit>:<path>`."""
    rev = word.split(":", 1)[0]
    return len(rev) >= 7 and (rev.startswith(commit) or commit.startswith(rev))


def git_past(sub: str, args: list[str], commit: str) -> bool:
    """Whether the `git` read `sub` with the arguments `args` reads at a
    revision other than `commit`, at none, or through a ref option. A word
    before `--` that is no option, no option's value and none of the
    subcommand's own non-revision words counts as a revision."""
    if sub == "status":
        return True
    valued = VALUED.get(sub, frozenset())
    revisions: list[str] = []
    i = 0
    pattern = sub == "grep"
    while i < len(args) and args[i] != "--":
        a = args[i]
        if a.startswith(REF_OPTIONS):
            return True
        if a in valued:
            if sub == "grep" and a in ("-e", "-f"):
                pattern = False
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        if pattern:
            pattern = False
        elif sub == "cat-file" and a in CAT_FILE_TYPES and not revisions:
            pass
        elif sub == "ls-tree" and revisions:
            pass
        else:
            revisions.append(a)
        i += 1
    return not revisions or not all(at_case(r, commit) for r in revisions)


def past_case(command: str, b: Bounds) -> str | None:
    """What the Bash command `command` reads past the case `b` gives, or
    None where it reads nothing past it."""
    from command_labels import programs
    from controlled_markdown import mctx

    if TRANSCRIPT_PATH.search(command):
        return mctx("it names a `.jsonl` file or a path under `.claude/projects/` or "
                    "`.claude-console/projects/`")
    for prog, args in programs(command):
        if prog == "transcripts.py" and (not args or args[0] != "window"
                                         or window_late(args[1:], b.time)):
            return mctx("it runs `transcripts.py` other than as `window` with an end no later "
                        "than the case's time")
        if prog == "git":
            sub, rest = git_subcommand(args)
            if sub in HISTORY and git_past(sub, rest, b.commit):
                return mctx("`git {sub}` reads other than at the case's commit alone").format(sub=sub)
    return None


def reason(what: str, b: Bounds) -> str:
    from controlled_markdown import mctx

    return "\n".join([
        mctx("Blocked: this call reads past the case's time or the case's commit that "
             "the `Trial bounds` line of your brief gives, since {what}.").format(what=what),
        mctx("In its place, read a transcript with `python3 "
             "~/.claude/skills/retrieve/transcripts.py window <start> <end> <session id>`, "
             "with an end no later than {time}, and a file the change under review does not "
             "edit with "
             "`git -C <worktree> show {commit}:<path>`.").format(time=b.time,
                                                                 commit=b.commit),
    ])


def check(hook: dict[str, Any]) -> str | None:
    """The reason to deny the Bash call `hook` gives where its caller is a
    trial and the call reads past the trial's case, and None otherwise."""
    from run_reads import caller_id, caller_transcript

    if caller_id(hook) is None:
        return None
    b = bounds(caller_transcript(hook))
    if b is None:
        return None
    what = past_case(hook["tool_input"]["command"], b)
    return None if what is None else reason(what, b)
