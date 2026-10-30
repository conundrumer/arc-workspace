#!/bin/bash
# Isolated zero-field INIT build. Refuse to reuse any installed environment.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source_tree="$(cd "$script_dir/../.." && pwd)"
cd "$source_tree/.."
destination="${1:-venv-s3-unit-v6}"
if [[ -e "$destination" ]]; then
    echo "Refusing existing environment: $destination; pass a fresh destination name." >&2
    exit 2
fi
export CARGO_TARGET_DIR="$PWD/target-perf"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}"
export PYTHONDONTWRITEBYTECODE=1
python_base="$PWD/venv-s3-unified/bin/python"
wheel_dir="$PWD/wheels-s3-unit-v6"
mkdir -p "$wheel_dir" run
started=$SECONDS
progress() {
    local elapsed=$((SECONDS-started))
    echo "unit-v6 build: done=$1/3 elapsed=${elapsed}s rate=$(awk -v n="$1" -v s="$elapsed" 'BEGIN {printf "%.3f", n/(s?s:1)}') steps/s $2" >&2
}
revision="$(git -C "$source_tree" rev-parse HEAD)"
progress 0 "engine=$revision destination=$destination"
maturin build --offline --profile tool --manifest-path "$source_tree/engine/arclog-py/Cargo.toml" --interpreter "$python_base" --out "$wheel_dir" &
build_pid=$!
trap 'kill "$build_pid" 2>/dev/null || true' INT TERM
while kill -0 "$build_pid" 2>/dev/null; do
    progress 0 "compiling pid=$build_pid"
    sleep 5
done
wait "$build_pid"
progress 1 wheel
"$python_base" -B -m venv "$destination"
progress 2 environment
uv pip install --python "$destination/bin/python" --no-deps "$wheel_dir/arclog-0.1.0-cp312-abi3-macosx_11_0_arm64.whl"
printf '%s\n' "$revision" > "$destination/engine-revision"
"$destination/bin/python" -B -c 'import arclog; print("isolated Unit-free extension:", arclog.__file__, flush=True)'
progress 3 installed
