"""Render a concept-decision deck into work/decks/, as the page the
Artifact tool publishes as it stands.

    uv run python scripts/concept_deck.py <name> <spec>.json [<spec>.json ...] [--title <title>]

One card per spec, in the order given; `study.deck_spec` states the spec.
The page is work/decks/<name>.html, titled `--title`, or `<name>` where
none is given. The command prints the path it wrote.
"""

import argparse
import sys
from pathlib import Path

from study.deck import write_deck
from study.deck_runs import run_card
from study.deck_spec import load_spec


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="concept_deck.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="the deck's file name under work/decks/")
    ap.add_argument("specs", nargs="+", type=Path, help="card spec JSON files")
    ap.add_argument("--title", help="the page's title; the name where none")
    args = ap.parse_args(argv)
    try:
        cards = [run_card(load_spec(p)) for p in args.specs]
        print(write_deck(args.name, args.title or args.name, cards))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
