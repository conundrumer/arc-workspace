#!/bin/bash
# Reruns the case choice of the stems round N regolded, then prune, view, check, census and bands.
G=/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-cover-forms-a036da074
H=/Users/davidlu/code/arc-workspace/scripts/run_heavy.py
cd "$G"; export GOLD_LIST=../gen-v3-11f6a212c/changed-gold-round$N.txt
cp -n round-out/case-choice.jsonl round-out/case-choice-before-round$N.jsonl
python3 - <<'P'
import json, os
st = set(open(os.environ["GOLD_LIST"]).read().split())
keep = [l for l in open('round-out/case-choice.jsonl') if json.loads(l)['stem'] not in st]
open('round-out/case-choice.new', 'w').writelines(keep)
os.replace('round-out/case-choice.new', 'round-out/case-choice.jsonl')
print(len(keep), 'case rows kept')
c = json.load(open('round-out/case-counts.json'))
for t in st:
    c[t] = sorted(f[:-7] for f in os.listdir('../gen-v3-11f6a212c/corpus/gen/cases/' + t) if f.endswith('.arclog'))
json.dump(c, open('round-out/case-counts.json', 'w'))
print({t: len(c[t]) for t in st})
P
step() { echo "$(date +%T) $1"; shift; "$@"; echo "$(date +%T) exit $?"; }
step case timeout 1500 $H --need soon $G/gold_cover_env.sh gold_cheapest_case.py run round-out/case-counts.json >> gold_cheapest_case.log 2>&1
tail -9 round-out/case-choice.jsonl | python3 -c "
import json,sys
for l in sys.stdin:
    r=json.loads(l); print(r['stem'], r.get('cases'), r.get('taken'), str(r.get('why'))[:80])"
step prune timeout 1500 $H --need soon $G/gold_cover_env.sh gold_cheapest_prune.py run > gold_cheapest_prune.log 2>&1
tail -1 gold_cheapest_prune.log | cut -c1-200
python3 gold_cover_view.py --dry | tail -1 | cut -c1-400
python3 gold_cover_view.py | tail -1 | cut -c1-300
SAMPLER_CORPUS=$G/corpus-view/ timeout 600 $H --need soon $G/gold_cover_env.sh gold_cover_check.py 12 2>&1 | tail -3 | cut -c1-200
step census timeout 1500 $H --need soon $G/gold_cover_env.sh gold_cover_census.py > gold_cover_census.log 2>&1
tail -3 gold_cover_census.log | cut -c1-300
rm -f round-out/bands-rows.jsonl
step bands timeout 1500 $H --need soon $G/gold_cover_env.sh gold_cheapest_bands.py run > gold_cheapest_bands.log 2>&1
tail -6 gold_cheapest_bands.log | cut -c1-300
