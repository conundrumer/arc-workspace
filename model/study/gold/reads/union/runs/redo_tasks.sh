#!/bin/bash
# usage: redo_tasks.sh SET "TASK ..."
# Drops the tasks from the fits and union shard files of SET, then runs them again: fits (FITS_CAP=300, shard 9 of 10), merge of the fits, union rows in 6 shards, merge of the union, union keys in 6 shards and their merge. Then prints, for each task, its pinned program's fit, how many programs solve it, and its union row. SITE (default site-exp29) is the engine on PYTHONPATH. Logs go to $UNION_SCRATCH (default: the scratchpad of session 64993706); the keys shards go to keys-shards there. The outputs are in work/lm/data-study/gold/gold-union.
cd /Users/davidlu/code/arc-workspace
S=${UNION_SCRATCH:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad}
SITE=${SITE:-/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/site-exp29}
G=$PWD/model/study/gold/reads/union; E=model/study/gold/cover_forms/gold_union_env.sh; O=work/lm/data-study/gold/gold-union
python3 - "$1" "$2" <<'PY'
import json, glob, sys
s, want = sys.argv[1], set(sys.argv[2].split())
O = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
for pat in ('fits-%s-[0-9]*.jsonl', 'union-%s-[0-9]*.jsonl'):
    for p in glob.glob(O + pat % s):
        ls = open(p).readlines(); keep = [l for l in ls if json.loads(l).get('t') == 'header' or json.loads(l)['task'] not in want]
        if len(keep) < len(ls): open(p, 'w').writelines(keep)
PY
FITS_CAP=300 FITS_TASKS="$2" ARCLOG_IDENT_SOURCE=value PYTHONPATH=$SITE scripts/run_heavy.py --need soon .venv/bin/python $G/gold_union_fits.py $1 9 10 > $S/redo-fits-$1.log 2>&1
ARCLOG_IDENT_SOURCE=value PYTHONPATH=$SITE .venv/bin/python $G/gold_union_fits.py $1 merge
UNION_TASKS="$2" scripts/run_heavy.py --need soon $E $G/gold_union.py run 0 6 $1 > $S/redo-union-$1.log 2>&1
$E $G/gold_union.py merge $1 | tail -1
for k in 0 1 2 3 4 5; do scripts/run_heavy.py --need soon $E $G/gold_union_keys.py $1 $k 6 > $S/keys-$1-$k.log 2>&1 & done; wait
$E $G/gold_union_keys.py $1 merge | tail -1
mkdir -p $S/keys-shards; mv $O/union-keys-$1-[0-9]*.jsonl $S/keys-shards/ 2>/dev/null
python3 - "$1" "$2" <<'PY'
import json, sys
s, want = sys.argv[1], set(sys.argv[2].split())
O = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
for l in open(O + 'fits-%s.jsonl' % s):
    r = json.loads(l)
    if r.get('t') == 'header':
        continue
    if r['task'] in want:
        print(r['task'], 'pinned', [(x['fit'], x['test_ok'], x['why']) for x in r['programs'] if 'pinned' in x['cases']], 'solve', sum(bool(x['fit'] and x['test_ok']) for x in r['programs']), 'of', len(r['programs']))
for l in open(O + 'union-%s.jsonl' % s):
    r = json.loads(l)
    if r['task'] in want:
        print(r['task'], 'union', r.get('error'), len(r.get('programs', {})), len(r.get('tables', [])))
print(open(O + 'union-%s.jsonl.sha256' % s).read().strip()[:8])
PY
