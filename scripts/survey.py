"""Survey one lib proposals entry and file the result in it.

    uv run python scripts/survey.py <entry>

A run that starts prints its run directory and the `session.log` under it. A
run may take up to an hour; when it ends, the entry holds the report under
a `Survey:` line of its own.

The scope is every solver when the entry holds no result, and otherwise
the solvers written since the entry's newest `Survey:` time. An entry with no
such solver is current, and the command runs nothing. A closed entry is
refused.
"""

import argparse
import sys

from handbook.paths import console_importable

console_importable()

from solver_console import surveys  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entry", help="a path under docs/wf-solver/proposals/, "
                                  "or the entry's name")
    ap.add_argument("--force", action="store_true",
                    help="survey a closed entry")
    args = ap.parse_args(argv)
    path = surveys.entry_path(args.entry)
    if not surveys.in_proposals(path):
        print(f"{path} is not an entry: the entries are the files under "
              f"{surveys.proposals_dir()}.", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"no entry at {path}", file=sys.stderr)
        return 1
    return surveys.survey_entry(path, force=args.force)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
