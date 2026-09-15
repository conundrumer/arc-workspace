"""Render the HTML cards the user rules on, into .scratch/cards/.

    uv run python scripts/cards.py theta            # the Θ card for 5d2a5c43
    uv run python scripts/cards.py render spec.json # any card spec
    uv run python scripts/cards.py calibration --from <compare.md>
"""

import argparse
import sys

from study.cards import calibration_cards, load_card, theta_card, write


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="cards.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("theta", help="render the Θ card for 5d2a5c43")
    render = sub.add_parser("render", help="render a card spec")
    render.add_argument("spec", help="path to a card spec JSON file")
    calibration = sub.add_parser("calibration", help="render a calibration card")
    calibration.add_argument("--from", dest="source", required=True,
                             help="path to a compare.md")
    args = ap.parse_args(argv)

    if args.cmd == "calibration":
        for path in calibration_cards(args.source):
            print(path)
        return 0
    card = theta_card() if args.cmd == "theta" else load_card(args.spec)
    print(write(card))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
