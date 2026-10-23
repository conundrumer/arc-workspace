#!/usr/bin/env bash
# Lists the ids of tasks that have no programs/solvers/<id>.dl; see unported_tasks.py.
exec uv run python "$(dirname "$0")/unported_tasks.py" "$@"
