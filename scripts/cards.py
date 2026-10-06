"""Render the HTML cards the user rules on, into work/cards/, as pages the
Artifact tool publishes as they stand.

    uv run python scripts/cards.py theta            # the Θ card for 5d2a5c43
    uv run python scripts/cards.py render spec.json # any card spec
    uv run python scripts/cards.py bundle <name> <page>.html <page>.html ...

`bundle` writes work/cards/<name>.html, one page that lists the rendered
card pages it is given and then holds each, in the order given. It takes
two pages or more, since one card's page is published as it stands, and a
name that is one file name. It runs no solver, and it fails on a page the
current renderer did not write.
"""

import argparse
import sys
from pathlib import Path

from study.card_spec import load_card
from study.card_runs import outside_solvers, solver_file
from study.cards import write, write_bundle
from study.theta_card import theta_card


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="cards.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("theta", help="render the Θ card for 5d2a5c43")
    render = sub.add_parser("render", help="render a card spec")
    render.add_argument("spec", help="path to a card spec JSON file")
    bundle = sub.add_parser("bundle", help="bundle rendered card pages")
    bundle.add_argument("name", help="the bundle's name and title")
    bundle.add_argument("pages", nargs="+", type=Path,
                        help="paths to rendered card pages")
    args = ap.parse_args(argv)

    if args.cmd == "bundle":
        try:
            print(write_bundle(args.name, args.pages))
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
        return 0
    card = theta_card() if args.cmd == "theta" else load_card(args.spec)
    path = solver_file(card)
    if outside_solvers(path):
        print(f"{path}: the checker reads solvers under programs/solvers/ "
              "alone", file=sys.stderr)
        return 2
    print(write(card))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
