"""File an issue in the form agents launched before tickets were given, as a
ticket under the main tree's `tickets/open/`. `file_ticket.LEGACY_HELP`,
which `--help` prints, says how an agent calls it."""

import sys

from file_ticket import legacy_main

if __name__ == "__main__":
    sys.exit(legacy_main(sys.argv[1:]))
