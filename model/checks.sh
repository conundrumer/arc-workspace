#!/usr/bin/env bash
# Runs the encoder's correctness checks at once, as separate processes, and prints PASS or FAIL for each with its
# wall time, and the output of each that fails. A check passes when it exits 0 and prints no FAIL. Exits 1 if any
# check fails. --full runs encoder_check.py on the whole dev export. A portability check of the files that go to the
# pod runs first: it prints PASS portability, or FAIL portability and the line, for each machine-specific name. The
# repo's document check (`controlled_markdown check`), which refuses a merge when it fails, runs with the rest.
#
#     [LM_PYTHON=<python>] [LM_TABLES=<dev export>] model/checks.sh [--full]
#
# LM_PYTHON defaults to work/lm/.venv/bin/python and LM_TABLES to work/tables/dev.
set -u
cd "$(dirname "$0")/.."
PY=${LM_PYTHON:-work/lm/.venv/bin/python}
TABLES=${LM_TABLES:-work/tables/dev}
LIMIT=${CHECK_TIMEOUT:-600}
ENC_ARGS=()
[ "${1:-}" = "--full" ] && ENC_ARGS=(--full)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
now() { "$PY" -c 'import time; print(time.time())'; }

run() {   # name, command...
    local name=$1; shift
    local t0; t0=$(now)
    timeout "$LIMIT" "$@" > "$tmp/$name.out" 2>&1
    echo $? > "$tmp/$name.code"
    "$PY" -c "import time; print(f'{time.time() - $t0:.1f}')" > "$tmp/$name.time"
}

export HF_HUB_OFFLINE=1
# The checks run small tensors; more threads only contend. Under `scripts/run_heavy.py` each check gets its share of
# `ARC_HEAVY_CPUS` (the gate sets OMP_NUM_THREADS to the whole of it), at least 1 and at most 2.
CHECKS=5   # the checks started at once below
threads=2
if [ -n "${ARC_HEAVY_CPUS:-}" ]; then
    threads=$((ARC_HEAVY_CPUS / CHECKS))
    [ "$threads" -lt 1 ] && threads=1
    [ "$threads" -gt 2 ] && threads=2
fi
export OMP_NUM_THREADS=$threads
run encoder_check "$PY" model/encoder_check.py "$TABLES" ${ENC_ARGS[@]+"${ENC_ARGS[@]}"} &
run insertion_check "$PY" model/insertion_check.py model/data-dev "$TABLES" &
run regression_check "$PY" model/regression_check.py &
run value_check "$PY" model/value_check.py --tables="$TABLES" &
run documents uv run python -m controlled_markdown check &
wait

failed=0
# a line with a machine-specific name fails; the two `getmtime` lines of `table_stamp` in encoder.py are allowed
portability=0
for f in encoder train pretrain encoder_check insertion_check regression_check value_check value_eval value_probe rollout_labels export_rollouts; do
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        portability=1
        echo "FAIL portability: model/$f.py:${hit%%:*}:${hit#*:}"
    done < <(grep -nE 'os\.path\.abspath|getmtime|/Users/|/workspace/|gethostname|expanduser' "model/$f.py" \
             | grep -vF -e 'int(os.path.getmtime' -e 'int(max(os.path.getmtime(f) for f in tasks.glob')
done
[ "$portability" = 0 ] && echo "PASS portability" || failed=1
for name in encoder_check insertion_check regression_check value_check documents; do
    code=$(cat "$tmp/$name.code")
    if [ "$code" = 0 ] && ! grep -q FAIL "$tmp/$name.out"; then
        echo "PASS $name ($(cat "$tmp/$name.time")s)"
    else
        failed=1
        echo "FAIL $name ($(cat "$tmp/$name.time")s, exit $code)"
        sed 's/^/    /' "$tmp/$name.out"
    fi
done
exit $failed
