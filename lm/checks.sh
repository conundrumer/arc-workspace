#!/usr/bin/env bash
# Runs the encoder's correctness checks at once, as separate processes, and prints PASS or FAIL for each with its
# wall time, and the output of each that fails. A check passes when it exits 0 and prints no FAIL. Exits 1 if any
# check fails. --full runs encoder_check.py on the whole dev export. A portability check of the files that go to the
# pod runs first: it prints PASS portability, or FAIL portability and the line, for each machine-specific name.
#
#     lm/checks.sh [--full]
set -u
cd "$(dirname "$0")/.."
PY=work/lm/.venv/bin/python
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
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-2}   # the checks run small tensors; more threads only contend
run encoder_check "$PY" lm/encoder_check.py ${ENC_ARGS[@]+"${ENC_ARGS[@]}"} &
run insertion_check "$PY" lm/insertion_check.py &
run regression_check "$PY" lm/regression_check.py &
run value_check "$PY" lm/value_check.py &
wait

failed=0
# a line with a machine-specific name fails; the two `getmtime` lines of `table_stamp` in encoder.py are allowed
portability=0
for f in encoder train pretrain encoder_check insertion_check regression_check value_check value_eval rollout_labels; do
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        portability=1
        echo "FAIL portability: lm/$f.py:${hit%%:*}:${hit#*:}"
    done < <(grep -nE 'os\.path\.abspath|getmtime|/Users/|/workspace/|gethostname|expanduser' "lm/$f.py" \
             | grep -vF -e 'int(os.path.getmtime' -e 'int(max(os.path.getmtime(f) for f in tasks.glob')
done
[ "$portability" = 0 ] && echo "PASS portability" || failed=1
for name in encoder_check insertion_check regression_check value_check; do
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
