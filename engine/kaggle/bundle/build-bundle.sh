#!/bin/bash
# build-bundle.sh CONFIG [STEPS]: builds the next kernel bundle and its soak kit from CONFIG (JSON). See config-example.json for the fields and bundle_steps.py for the steps.
# STEPS is a comma list of step numbers, or N:name for one check of step 6. The default is every step. It stops at the first failed pass condition and forces nothing.
here=$(cd "$(dirname "$0")" && pwd)
[ -n "$1" ] || { sed -n 2,3p "$0"; exit 2; }
exec python3 "$here/bundle_steps.py" "$@"
