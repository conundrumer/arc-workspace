#!/bin/bash
# Isolated build/install only. Run via engine/scripts/run_heavy.py.
set -euo pipefail
cd "$(dirname "$0")/../.."
export CARGO_TARGET_DIR="$PWD/target-perf"
export PYTHONDONTWRITEBYTECODE=1
PYTHON_BASE="$PWD/venv/bin/python"
mkdir -p wheels-perf run
started=$SECONDS
maturin build --offline --profile tool --manifest-path engine-perf/engine/arclog-py/Cargo.toml --interpreter "$PYTHON_BASE" --out "$PWD/wheels-perf" &
build_pid=$!
trap 'kill "$build_pid" 2>/dev/null || true' INT TERM
while kill -0 "$build_pid" 2>/dev/null; do
    echo "stage3-perf build: elapsed=$((SECONDS-started))s, pid=$build_pid" >&2
    sleep 5
done
wait "$build_pid"
"$PYTHON_BASE" -B -m venv "$PWD/venv-perf"
uv pip install --python "$PWD/venv-perf/bin/python" --no-deps --reinstall "$PWD/wheels-perf/arclog-0.1.0-cp312-abi3-macosx_11_0_arm64.whl"
"$PWD/venv-perf/bin/python" -B -c 'import arclog; print("isolated extension:", arclog.__file__, flush=True)'
