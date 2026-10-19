"""Rewrite sections of docs/engine/corpus-survey.md from the corpus.

    uv run python scripts/corpus_survey.py                 # every section that runs no solver
    uv run python scripts/corpus_survey.py <section> ...   # the sections named

Each section is rewritten in place, found by its heading; the other
sections stay as the file holds them. A section marked slow runs Souffle
or a solver, and runs only when its name is given; it keeps what it
computes per solver under .cache/corpus-survey/<section>/ of the main
worktree, so that its next run computes again only for the solvers whose
files changed. Run a section only where a decision needs its numbers on
the current corpus.

The sections, by name:

{sections}
"""

import argparse
import sys

from study.corpus_survey.document import SECTIONS, by_name, rewrite


def usage() -> str:
    return (__doc__ or "").format(sections="\n".join(
        f"    {s.name}{' (slow)' if s.slow else ''}" for s in SECTIONS))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="corpus_survey.py", description=usage(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sections", nargs="*", metavar="section")
    args = ap.parse_args(argv)
    try:
        chosen = [by_name(n) for n in args.sections] if args.sections else [s for s in SECTIONS if not s.slow]
    except KeyError as e:
        print(f"corpus_survey.py: no section is named {e.args[0]}", file=sys.stderr)
        return 2
    rewrite(chosen)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
