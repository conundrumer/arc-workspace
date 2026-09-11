"""Survey one lib proposals entry and file the result in it.

    uv run python scripts/survey.py <entry>

The entry is a path under docs/wf-solver/proposals/, or an entry's name. A run
that starts prints its run directory and the `session.log` under it, so the
operator can follow the session. A run may take up to an hour, the timeout
`solver_console.config.SURVEY_TIMEOUT` sets; when it ends, the entry carries
the report under a `Survey:` line of its own.

The scope is every solver when the entry carries no result, and otherwise
the solvers written since the entry's newest `Survey:` time. An entry with no
such solver is current, and the command runs nothing. A closed entry is
refused; `--force` surveys it anyway.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "console"))

from solver_console import surveys  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
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
