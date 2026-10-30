#!/bin/bash
# Combined checked-IR, replay, bounded-cache and resume wheel. No tests.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source_tree="$(cd "$script_dir/.." && pwd)"
cd "$source_tree/.."
export CARGO_TARGET_DIR="$PWD/target-perf"
export PYTHONDONTWRITEBYTECODE=1
python_base="$PWD/venv/bin/python"
mkdir -p wheels-s3-unified run
started=$SECONDS
maturin build --offline --profile tool --manifest-path "$source_tree/engine/arclog-py/Cargo.toml" --interpreter "$python_base" --out "$PWD/wheels-s3-unified" &
build_pid=$!
trap 'kill "$build_pid" 2>/dev/null || true' INT TERM
while kill -0 "$build_pid" 2>/dev/null; do
    echo "stage3-unified build: elapsed=$((SECONDS-started))s, pid=$build_pid" >&2
    sleep 5
done
wait "$build_pid"
"$python_base" -B -m venv "$PWD/venv-s3-unified"
uv pip install --python "$PWD/venv-s3-unified/bin/python" --no-deps --reinstall "$PWD/wheels-s3-unified/arclog-0.1.0-cp312-abi3-macosx_11_0_arm64.whl"
"$PWD/venv-s3-unified/bin/python" -B -c 'import arclog; assert hasattr(arclog.StudyTaskEvaluator, "finish_case") and hasattr(arclog.StudyTaskEvaluator, "replay"); print("unified extension:", arclog.__file__, flush=True)'
