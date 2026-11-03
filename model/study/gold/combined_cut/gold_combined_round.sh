#!/bin/bash
# After a round's cover stage: runs the extended cut and the shape cut on the round's stems from their text in gold-v3-cheapest-round50, then rebuilds view-final, then runs the DAG split second pass on those stems from their view-final text (rows in gold-v3-dag-bits/cut2-r<n>/) and rebuilds view-final.
# usage: gold_combined_round.sh <round number> <stem>...
n=$1; shift
G=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut
out=$G/mac-r$n; mkdir -p "$out"
cd "$G" || exit 1
python3 - "$out" "$@" <<'P'
import gzip, json, os, sys
out, stems = sys.argv[1], sys.argv[2:]
base = '../gold-v3-cover-forms-a036da074/'
points = {p['task']: p['gold_sexp'] for p in json.load(open(base + 'points-eval.json'))}
lines = {}
for t in stems:
    p = base + 'corpus-view/%s/pairs.jsonl.gz' % t
    if os.path.exists(p):
        with gzip.open(p, 'rt') as f:
            lines[t] = json.loads(f.readline())['gold_sexp'].splitlines()
    elif t in points:
        lines[t] = points[t].splitlines()
json.dump(lines, open(out + '/lines.json', 'w'))
json.dump({}, open(out + '/weights.json', 'w'))
open(out + '/tasks.txt', 'w').write('\n'.join(lines) + '\n')
P
ORCUT_KEPT_NODES=48 /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 2 --need soon "$G/code/gold_combined_env.sh" gold_combined_run.py "$out/tasks.txt" "$out/lines.json" "$out/weights.json" "$out/rows-0.jsonl" 0 1 > "$out/run.log" 2>&1
echo "combined exit $?"
python3 gold_combined_view.py "$G/view-final" | tail -1 | cut -c1-300
d=$G/../gold-v3-dag-bits/cut2-kit; o=$G/../gold-v3-dag-bits/cut2-r$n; mkdir -p "$o"
for t in "$@"; do
  python3 - "$t" "$o/lines-$t.json" <<'P'
import gzip, json, sys
t, out = sys.argv[1:]
with gzip.open('view-final/%s/pairs.jsonl.gz' % t, 'rt') as f:
    json.dump({t: json.loads(f.readline())['gold_sexp'].splitlines()}, open(out, 'w'))
P
  DAG_START_READ=1 timeout 900 /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon bash "$d/gold_dagcut2_env.sh" gold_dagcut2_one.py "$t" "$o/lines-$t.json" 840 >> "$o/rows-0.jsonl" 2>> "$o/rows-0.log"
done
echo "dag split exit $?"
python3 gold_combined_view.py "$G/view-final" | tail -1 | cut -c1-300
