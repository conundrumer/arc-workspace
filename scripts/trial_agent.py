"""Write the agent type a doc reviewer's trial of a reader at a change runs
as, and wait until a trial's system prompt stands in the prompt cache, as
HELP gives."""

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from controlled_markdown import Registry, mctx
from controlled_markdown.renderers import render
from engine import checkout
from handbook.agents import agent_meta
from handbook.paths import scripts_importable
from handbook.reader_names import ReaderName
from handbook.readers import context_text, reader_named
from operations.roles import Model

scripts_importable()

from state_reads import new_state  # noqa: E402
from ticket_files import ticket_path, ticket_status  # noqa: E402
from ticket_numbers import SESSION_VAR, TicketNumber, matched_number, ticket_number  # noqa: E402
from ticketing.vocabulary import TICKET_NUMBER, Status  # noqa: E402
from transcript_entries import Refused, entries_forward, print_refused  # noqa: E402
from transcripts import find  # noqa: E402
from tree_reads import main_tree  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/trial_agent.py write <change number> <reader> [args]  # write the trial type of that reader at that change
        uv run python scripts/trial_agent.py cached <agent id>                      # wait until that agent's system prompt is cached
        uv run python scripts/trial_agent.py --help | -h                            # print this text
        ```
    - Run each form in the change's worktree.
    - `write` writes the agent type `trial-<change number>-<reader slug>-<hash>` to `.claude/agents/` of the main tree, the parent of `git rev-parse --path-format=absolute --git-common-dir`, and prints its name.
        - `<reader slug>` is `<reader>` and each of `[args]`, joined by `-`.
        - `<hash>` is the first 8 hex digits of the sha256 of the type's file text with its `name` line left out.
        - Its system prompt is the worktree's `CLAUDE.md`, rendered and given as in force in place of the `CLAUDE.md` the agent loads, then what `uv run python scripts/context.py context <reader> [args]` prints in the worktree.
        - Its front matter gives `name`, a `description` that gives it as the trial of that reader at that change, launched by that change's doc reviewer alone, `model` and `tools: Read, Grep, Glob, Bash`.
            - For `agent <name>`, `model` is the `model` of the front matter of that agent's prompt under `prompts/agents/`.
            - For `coordinator`, `user-session` and `session`, it is the alias of the family of the `message.model` of the last assistant entry of the transcript of the session `$CLAUDE_CODE_SESSION_ID` gives.
            - For any other reader, and where no model is found, the command refuses and writes nothing.
        - Where that file stands already, it writes nothing.
        - It then removes each other `trial-<change number>-<reader slug>-<hash>.md` there, and prints each after `removed`.
        - It then removes each `trial-<n>-*.md` there whose ticket `<n>` stands under `tickets/closed/` of the main tree, and prints each after `removed`.
    - `cached` ends once the transcript of that agent holds its first assistant entry, and prints nothing.
    - A form that refuses prints the reason after `refused:` on stderr and exits 1.
    """)

TOOLS = "Read, Grep, Glob, Bash"
"""The tools of a trial: no `Agent`, `Edit` or `Write`, so a trial launches
no agent and writes no file by a tool of its own."""

TRIAL_PREFIX = "trial-"
"""The opening of the name of each trial type."""

HASH_DIGITS = 8

HASH = rf"[0-9a-f]{{{HASH_DIGITS}}}"

TRIAL = re.compile(rf"{TRIAL_PREFIX}(?P<number>{TICKET_NUMBER.pattern})-(?P<slug>[a-z].*)-{HASH}\.md")
"""A trial type's file: its slug opens with a reader's name, so the number
ends at the last `-` before a letter."""

SESSION_READERS = (ReaderName.COORDINATOR, ReaderName.USER_SESSION, ReaderName.SESSION)
"""The readers that run on the model of the session's coordinator."""

POLL_SECONDS = 0.5


def is_trial(agent_type: str) -> bool:
    return agent_type.startswith(TRIAL_PREFIX)


def stem(number: TicketNumber, reader: str, args: list[str]) -> str:
    """The name of the reader's trial type at the change, less its hash."""
    return TRIAL_PREFIX + "-".join([str(number), reader, *args])


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
    raise Refused(mctx("`write` finds no model for the reader `{reader}`: `--help` gives the readers it takes").format(
        reader=" ".join([reader, *args])))


def instructions() -> str:
    """The worktree's `CLAUDE.md` as `controlled_markdown render` prints it."""
    registry = Registry(checkout.ROOT)
    return render(registry.load(checkout.ROOT / "CLAUDE.md", name="CLAUDE.md"), registry)


def definition(number: TicketNumber, reader: str, args: list[str]) -> tuple[str, str]:
    """The name and the file text of the reader's trial type at the change.
    The name ends in a hash of the text less its `name` line, so a new text
    is a new type, which the harness cannot serve with an old one's."""
    description = mctx("The trial of the reader `{reader}` at change {number}, "
                       "which only that change's doc reviewer launches.").format(
        reader=" ".join([reader, *args]), number=number)
    # The model is looked up before the context renders, so a reader with no
    # model refuses at once.
    model = reader_model(reader, args)
    context = context_text(reader_named(reader), args)
    lead = mctx("Your instructions are the `CLAUDE.md` between the lines `<claude-md>` "
                "and `</claude-md>` below, in force in place of the `CLAUDE.md` you load, "
                "and then the text after those lines.")
    fields = [f"description: {json.dumps(description)}", f"model: {model}", f"tools: {TOOLS}"]
    prompt = f"{lead}\n\n<claude-md>\n{instructions()}</claude-md>\n\n{context}"

    def text(front: list[str]) -> str:
        return "\n".join(["---", *front, "---", prompt])

    digest = hashlib.sha256(text(fields).encode()).hexdigest()[:HASH_DIGITS]
    name = f"{stem(number, reader, args)}-{digest}"
    return name, text([f"name: {name}", *fields])


def closed_trials(agents: Path, tickets: Path) -> list[Path]:
    """Each trial type's file under `agents` whose change's ticket stands
    under `closed`."""
    out = []
    for path in sorted(agents.glob(f"{TRIAL_PREFIX}*.md")):
        if (m := TRIAL.fullmatch(path.name)) and \
                ticket_status(ticket_path(tickets, matched_number(m))) is Status.CLOSED:
            out.append(path)
    return out


def write(number: TicketNumber, reader: str, args: list[str]) -> list[str]:
    tree = main_tree()
    agents = checkout.agents_of(tree)
    name, text = definition(number, reader, args)
    path = agents / f"{name}.md"
    if not path.is_file():
        agents.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    lines = [name]
    earlier = re.compile(rf"{re.escape(stem(number, reader, args))}-{HASH}\.md")
    replaced = [p for p in sorted(agents.glob(f"{TRIAL_PREFIX}*.md"))
                if p != path and earlier.fullmatch(p.name)]
    for old in [*replaced, *closed_trials(agents, tree / "tickets")]:
        old.unlink()
        lines.append(mctx("removed {name}").format(name=old.name))
    return lines


def cached(agent: str) -> None:
    """Waits for the agent's first assistant entry: its first request has
    then been answered, so the cache holds its system prompt."""
    while True:
        new_state()
        try:
            path = find(agent)
        except Refused:
            # No transcript yet: the agent has not started.
            path = None
        if path is not None and any(e.get("type") == "assistant"
                                    for e in entries_forward(path)):
            return
        time.sleep(POLL_SECONDS)


def main(args: list[str]) -> int:
    if not args or args[0] in ("--help", "-h"):
        print(HELP)
        return 0
    try:
        if args[0] == "write" and len(args) >= 3:
            print("\n".join(write(ticket_number(args[1]), args[2], args[3:])))
        elif args[0] == "cached" and len(args) == 2:
            cached(args[1])
        else:
            print(HELP, file=sys.stderr)
            return 2
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
