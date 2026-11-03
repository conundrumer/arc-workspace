#!/bin/bash
# nb-test.sh BUNDLE SITE TASKS SECONDS: runs the bundle's notebook cell with /kaggle paths moved under BUNDLE/nb, on the Mac engine SITE, with the wheels left out.
B=$(cd "$1" && pwd); SITE=$2; NT=${3:-2}; S=${4:-60}
R=/Users/davidlu/code/arc-workspace; SP=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/ede6795c-2b6f-4633-a6da-08e90de33bc4/scratchpad
PY=$R/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
N=$B/nb; rm -rf $N; mkdir -p $N/input/comp $N/working; cp -R $B/dataset $N/input/data; rm $N/input/data/*.whl
python3 - "$N" "$SP" "$B" "$SITE" "$NT" "$S" <<'PY'
import json, sys
N, L, B, SITE, nt, S = sys.argv[1:7]
c = json.load(open(L + '/comp/arc-agi_test_challenges.json'))
k = list(c)[:int(nt)]
json.dump({x: c[x] for x in k}, open(N + '/input/comp/arc-agi_test_challenges.json', 'w'))
rc = json.load(open(N + '/input/data/run_config.json')); rc.update(seconds=int(S), tasks=int(nt), rss_limit_mib=2888); json.dump(rc, open(N + '/input/data/run_config.json', 'w'))
s = ''.join(json.load(open(B + '/kernel/notebook.ipynb'))['cells'][0]['source'])
s = s.replace('/kaggle/working', N + '/working').replace('/kaggle/input', N + '/input').replace('/tmp/arc', N + '/arc')
a = "PYTHONPATH=ROOT + '/site:' + sampler"
assert a in s
s = s.replace(a, "PYTHONPATH=%r + ':' + sampler" % SITE)
open(N + '/cell.py', 'w').write(s)
PY
$R/scripts/run_heavy.py --cpus $NT --need now env PYTHONDONTWRITEBYTECODE=1 $PY -u $N/cell.py > $N/log.txt 2>&1; echo "== exit $?"
grep -E "challenges |tasks [0-9]+ workers|submission|Traceback|deaths|pool" $N/log.txt | grep -v "status at" | cut -c1-160 | tail -8
python3 -c "
import json;s=json.load(open('$N/working/submission.json'));print('tasks',len(s))"
echo "Traceback lines in the cell log $(grep -c Traceback $N/log.txt), in worker logs $(cat $N/arc/work/*.log | grep -c Traceback)"
grep -h 'pool clauses\|tree distribution\|steers off\|writer' $N/arc/work/*.log | sort | uniq -c | cut -c1-200 | head
grep -h '^end:\|^candidates' $N/arc/work/*.log | cut -c1-200 | head
