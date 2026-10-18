"""Run a doc reviewer's trial of a reader at a change as a `claude -p`
process that saves no session, and read what the trial did, as HELP
gives."""

import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from controlled_markdown import Registry, mctx
from controlled_markdown.renderers import render
from engine import checkout
from handbook.agent_documents import agent_meta
from handbook.paths import scripts_importable
from handbook.reader_names import ReaderName
from handbook.readers import context_text, reader_named
from operations.roles import Model

scripts_importable()

from claude_config import config_dir  # noqa: E402
from run_reads import text_of, tool_results  # noqa: E402
from ticket_numbers import SESSION_VAR, TicketNumber, ticket_number  # noqa: E402
from transcript_entries import blocks, entries_forward  # noqa: E402
from transcript_snapshots import Refused, print_refused  # noqa: E402
from transcripts import find  # noqa: E402
from trial_bounds_check import bounds  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/trial_agent.py run <change number> <reader> [args] <case time> <case commit>  # run a trial of that reader at that change, with its brief on stdin
        uv run python scripts/trial_agent.py cached <output file>                                           # wait until that trial's system prompt is cached
        uv run python scripts/trial_agent.py calls <output file>                                            # print that trial's calls, its reply and its cache figures
        uv run python scripts/trial_agent.py --help | -h                                                    # print this text
        ```
    - Run each form in the change's worktree.
    - `run` runs `claude -p` on the brief, with no session saved, and ends when that run ends, with its exit code.
        - It prints the path of the trial's output file at its start: the run's `stream-json` output, under `.cache/trials/` of the worktree.
        - The run's model is the reader's model.
            - For `agent <name>`, it is the `model` of the front matter of that agent's prompt under `prompts/agents/`.
            - For `coordinator`, `user-session` and `session`, it is the alias of the family of the `message.model` of the last assistant entry of the transcript of the session `$CLAUDE_CODE_SESSION_ID` gives.
            - For any other reader, and where no model is found, the command refuses and runs nothing.
        - The trial's shared part is the file `.cache/trials/<change number>-<reader slug>.md` of the worktree.
            - `<reader slug>` is `<reader>` and each of `[args]`, joined by `-`.
            - The shared part is a lead, then the user's global `CLAUDE.md` of the Claude config directory (`$CLAUDE_CONFIG_DIR`, or `~/.claude` where that is unset), then the worktree's `CLAUDE.md` as `uv run python -m controlled_markdown render CLAUDE.md` prints it, then what `uv run python scripts/context.py context <reader> [args]` prints in the worktree.
            - For `agent <name>`, the shared part is the run's whole system prompt, and for the session readers it is appended to Claude Code's own.
            - Where the user's global `CLAUDE.md` does not exist, the command refuses and runs nothing.
        - The run has each of the tools `Read`, `Grep`, `Glob` and `Bash` that its reader has, no setting source, no plugin and no claude.ai connector, the permission mode `auto`, and one hook: `scripts/trial_bounds_check.py` with the case time and the case commit, on each Bash call.
            - Where the case time is not `YYYY-MM-DDTHH:MM:SSZ` in UTC, or the case commit is not 7 to 40 hex digits, the command refuses and runs nothing.
    - `cached` ends once that output file holds its first `assistant` event, and prints nothing.
        - Where the file holds a `result` event and no `assistant` event, it refuses.
    - `calls` prints each tool call of the trial with its result, then the trial's reply, then the `cache_creation_input_tokens` and the `cache_read_input_tokens` of its first request.
    - A form that refuses prints the reason after `refused:` on stderr and exits 1.
    """)

TOOLS = ("Read", "Grep", "Glob", "Bash")
"""The tools a trial may have: no `Agent`, `Edit` or `Write`, so a trial
launches no agent and writes no file by a tool of its own."""

PLUGIN_VAR = "CLAUDE_CODE_PLUGIN_DIRS"
"""The variable by which a plugin's tools and hooks reach a `claude -p`
run, which `--setting-sources ''` does not keep out."""

CACHE_TTL_VAR = "CLAUDE_CODE_PROMPT_CACHE_TTL"
"""Sets the prompt-cache TTL of a `claude -p` run. Unset, a run on a Claude
subscription gets the 1-hour TTL, which costs more than the 5-minute one."""

SESSION_READERS = (ReaderName.COORDINATOR, ReaderName.USER_SESSION, ReaderName.SESSION)
"""The readers that run on the model of the session's coordinator."""

POLL_SECONDS = 0.5


SYSTEM_PROMPT_FLAG = {"agent": "--system-prompt-file",
                      **{r: "--append-system-prompt-file" for r in SESSION_READERS}}
"""The flag that gives the shared part to a trial of each reader: a
subagent's system prompt holds none of Claude Code's main-session prompt,
and a session's holds it."""

def family(model: str) -> Model:
    """The `Model` alias whose family `model`, a `message.model` such as
    `claude-opus-5-5`, gives."""
    found = [m for m in Model if m.value in model.split("-")]
    if len(found) != 1:
        raise Refused(mctx("`{model}` holds not exactly one of the model families {families}").format(
            model=model, families=", ".join(Model)))
    return found[0]


def session_model() -> Model:
    session = os.environ.get(SESSION_VAR)
    if not session:
        raise Refused(mctx("`${var}` is not set").format(var=SESSION_VAR))
    path = find(session)
    for e in reversed(list(entries_forward(path))):
        if e.get("type") == "assistant" and (model := e.get("message", {}).get("model")):
            return family(model)
    raise Refused(mctx("{path} holds no assistant entry with a model").format(path=path))


def reader_model(reader: str, args: list[str]) -> str:
    if reader == ReaderName.AGENT and len(args) == 1:
        model = agent_meta(args[0]).get("model")
        if model is None:
            raise Refused(mctx("the prompt of agent `{name}` gives no `model`").format(name=args[0]))
        return model
    if reader in SESSION_READERS and not args:
        return session_model().value
    raise Refused(mctx("`run` finds no model for the reader `{reader}`: `--help` gives the readers it takes").format(
        reader=" ".join([reader, *args])))


def instructions() -> str:
    """The worktree's `CLAUDE.md` as `controlled_markdown render` prints it."""
    registry = Registry(checkout.ROOT)
    return render(registry.load(checkout.ROOT / "CLAUDE.md", name="CLAUDE.md"), registry)


def reader_tools(reader: str, args: list[str]) -> list[str]:
    """Each of `TOOLS` that the reader has: an agent whose front matter
    gives no `tools` has every tool, as a session has."""
    given = agent_meta(args[0]).get("tools") if reader == ReaderName.AGENT else None
    if given is None:
        return list(TOOLS)
    own = {t.strip() for t in given.split(",")}
    return [t for t in TOOLS if t in own]


def trials_dir() -> Path:
    return checkout.ROOT / ".cache" / "trials"


def slug(reader: str, args: list[str]) -> str:
    return "-".join([reader, *args])


def must_exist(path: Path) -> None:
    if not path.is_file():
        raise Refused(mctx("{path} does not exist").format(path=path))


def shared_part(reader: str, args: list[str]) -> str:
    """The text that each trial of the reader at the change shares."""
    user = config_dir() / "CLAUDE.md"
    must_exist(user)
    context = context_text(reader_named(reader), args)
    lead = mctx("Below, the user's global instructions are between the lines "
                "`<user-claude-md>` and `</user-claude-md>`, and the project's instructions "
                "are between the lines `<project-claude-md>` and `</project-claude-md>`.")
    return (f"{lead}\n\n<user-claude-md>\n{user.read_text()}</user-claude-md>\n\n"
            f"<project-claude-md>\n{instructions()}</project-claude-md>\n\n{context}")


def write_shared(number: TicketNumber, reader: str, args: list[str]) -> Path:
    """The shared part's file, written where its text differs, by a rename,
    so that a trial that starts beside this one reads it whole."""
    path = trials_dir() / f"{number}-{slug(reader, args)}.md"
    text = shared_part(reader, args)
    if not path.is_file() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(f"{path.name}.{uuid.uuid4().hex}")
        part.write_text(text)
        part.replace(path)
    return path


def settings(case_time: str, case_commit: str) -> str:
    hook = shlex.join([sys.executable, str(checkout.ROOT / "scripts" / "trial_bounds_check.py"),
                       case_time, case_commit])
    return json.dumps({
        "permissions": {"defaultMode": "auto"},
        "disableClaudeAiConnectors": True,
        "hooks": {"PreToolUse": [{"matcher": "Bash",
                                  "hooks": [{"type": "command", "command": hook}]}]},
    })


def run(number: TicketNumber, reader: str, args: list[str], case_time: str, case_commit: str,
        brief: str) -> int:
    # The model is looked up before the context renders, so a reader with no
    # model refuses at once.
    model = reader_model(reader, args)
    shared = write_shared(number, reader, args)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = trials_dir() / f"{number}-{slug(reader, args)}-{stamp}-{uuid.uuid4().hex[:8]}.jsonl"
    print(out, flush=True)
    env = {k: v for k, v in os.environ.items() if k != PLUGIN_VAR} | {CACHE_TTL_VAR: "5m"}
    command = ["claude", "-p", "--no-session-persistence", "--model", model, "--tools", ",".join(reader_tools(reader, args)),
               "--output-format", "stream-json", "--verbose", "--setting-sources", "",
               "--settings", settings(case_time, case_commit), SYSTEM_PROMPT_FLAG[reader], str(shared)]
    with out.open("w") as f:
        return subprocess.run(command, input=brief, text=True, stdout=f, env=env,
                              cwd=checkout.ROOT).returncode


def events(path: Path) -> Iterator[dict[str, Any]]:
    """The events of the output file at `path`, each whole line of it: the
    last line may be one the run has not ended yet."""
    with path.open() as f:
        for line in f:
            if line.endswith("\n") and line.strip():
                yield json.loads(line)


def cached(path: Path) -> None:
    """Waits for the trial's first assistant event: its first request has
    then been answered, so the cache holds its system prompt."""
    while True:
        kinds = {e.get("type") for e in events(path)} if path.is_file() else set()
        if "assistant" in kinds:
            return
        if "result" in kinds:
            raise Refused(mctx("{path} holds a `result` event and no `assistant` event").format(
                path=path))
        time.sleep(POLL_SECONDS)


def indented(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


def calls(path: Path) -> list[str]:
    must_exist(path)
    found = list(events(path))
    results = {i: text for e in found for i, _, text in tool_results(e)}
    lines: list[str] = []
    for e in found:
        if e.get("type") != "assistant":
            continue
        for b in blocks(e, "tool_use"):
            lines.append(mctx("call {name} {input}").format(
                name=b["name"], input=json.dumps(b.get("input"))))
            lines.append(indented(results.get(b["id"], mctx("no result"))))
    reply = next((e for e in reversed(found) if e.get("type") == "result"), None)
    lines.append(mctx("reply"))
    lines.append(indented(text_of(reply.get("result")) if reply else mctx("no reply")))
    first = next((e for e in found if e.get("type") == "assistant"), None)
    usage = (first or {}).get("message", {}).get("usage", {})
    for field in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        lines.append(f"{field} {usage.get(field, '?')}")
    return lines


def check_bounds(time_: str, commit: str) -> None:
    if bounds(time_, commit) is None:
        raise Refused(mctx("`{time} {commit}` is not a case time in UTC as `YYYY-MM-DDTHH:MM:SSZ` "
                           "followed by a case commit of 7 to 40 hex digits").format(time=time_, commit=commit))


def main(args: list[str]) -> int:
    if not args or args[0] in ("--help", "-h"):
        print(HELP)
        return 0
    try:
        if args[0] == "run" and len(args) >= 5:
            check_bounds(args[-2], args[-1])
            return run(ticket_number(args[1]), args[2], args[3:-2], args[-2], args[-1],
                       sys.stdin.read())
        elif args[0] == "cached" and len(args) == 2:
            cached(Path(args[1]))
        elif args[0] == "calls" and len(args) == 2:
            print("\n".join(calls(Path(args[1]))))
        else:
            print(HELP, file=sys.stderr)
            return 2
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
