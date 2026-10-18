"""Print the items of an agent's checklist, one at a time. `--help` prints
HELP; `handbook.checklist` reads the checklist."""

import sys

from controlled_markdown import mctx
from handbook.checklist import Checklist

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/step.py <agent>                    # print the first item of the agent's checklist
        uv run python scripts/step.py <agent> <item>             # print the item after <item>
        uv run python scripts/step.py <agent> --enter <item>     # print the file of the conditional part <item> calls, then the first item under <item>
        uv run python scripts/step.py <agent> --reenter <item>   # print the first item under <item>, without the file of the part it calls
        uv run python scripts/step.py <agent> --stop <item>      # stop the walk at <item>, which you find no way to do: print the call that prints <item>, then the last item
        uv run python scripts/step.py --help | -h                # print this text
        ```
    - An item is given by its heading's text or by its id, the slug of that text.
    - [Checklists](prompts/agents/notes/checklists.md#checklists) gives the form of a checklist and what each call prints.
    """)


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("--help", "-h") or len(argv) > 3:
        print(HELP)
        raise SystemExit(0 if argv and argv[0] in ("--help", "-h") else 2)
    agent, rest = argv[0], argv[1:]
    match rest:
        case []:
            print(Checklist(agent).first())
        case ["--enter", item]:
            print(Checklist(agent).enter(item))
        case ["--reenter", item]:
            print(Checklist(agent).reenter(item))
        case ["--stop", item]:
            print(Checklist(agent).stop(item))
        case [item]:
            print(Checklist(agent).after(item))
        case _:
            print(HELP)
            raise SystemExit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
