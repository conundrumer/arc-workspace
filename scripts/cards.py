"""Render the HTML cards the user rules on, into work/cards/.

    uv run python scripts/cards.py theta            # the Θ card for 5d2a5c43
    uv run python scripts/cards.py render spec.json # any card spec
"""

import argparse
import sys

from study.card_spec import load_card
from study.card_runs import outside_solvers, solver_file
from study.cards import write
from study.theta_card import theta_card


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="cards.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("theta", help="render the Θ card for 5d2a5c43")
    render = sub.add_parser("render", help="render a card spec")
    render.add_argument("spec", help="path to a card spec JSON file")
    args = ap.parse_args(argv)

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
