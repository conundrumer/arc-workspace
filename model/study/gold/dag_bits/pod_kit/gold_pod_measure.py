"""Writes measured.json, the ETA of the pod run, from rows of the final code on the Mac (measured/rows-0.jsonl) and dag-kit's out99 rows.

  python3 gold_pod_measure.py

Rate: new CPU over old CPU on the measured stems whose text is dag-kit's, times dag-kit's CPU per weight unit over its 97 finished stems of the 99, times the weight of all stems, times 1.52 (pod CPU over Mac CPU, measured on the combined kit's stage), over 16 shards. The direct rate is the new CPU per weight unit on the measured stems, which are small, so it is the low end.
"""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
w = json.load(open(HERE + '/measured/weights.json'))
changed = set(json.load(open(HERE + '/scratch/changed.json')))
old = {}
for p in glob.glob(HERE + '/../dag-kit/out99/rows-*.jsonl'):
    for l in open(p):
        try:
            r = json.loads(l)
            old[r['task']] = r
        except json.JSONDecodeError:
            pass
ok = {t: r for t, r in old.items() if 'cpu' in r}
new = {}
for l in open(HERE + '/measured/rows-0.jsonl'):
    r = json.loads(l)
    new[r['task']] = r
same = [t for t in new if t in ok and t not in changed]
ratio = sum(new[t]['cpu'] for t in same) / sum(ok[t]['cpu'] for t in same)
pop = sum(r['cpu'] for r in ok.values()) / sum(w[t] for t in ok)
W = sum(w.values())
direct = sum(r['cpu'] for r in new.values()) / sum(w[t] for t in new)
hi = pop * ratio * W
lo = direct * W
m = dict(stems=[dict(task=t, weight=w[t], cpu=r['cpu'], wall=r['wall'], peak_gib=r['peak_gib'], peak_procs=r['peak_procs'], forms=len(r['forms']), cpu_walks=r['times'].get('walk'), cpu_prefix=r['times'].get('prefix'), cpu_canonical=r['times'].get('canonical'), stage_code=r['stage_code'], code=r['code'], old_cpu=ok[t]['cpu'] if t in ok and t not in changed else None) for t, r in new.items()],
         new_over_old_cpu=round(ratio, 2), old_cpu_per_weight_99=round(pop, 4), direct_cpu_per_weight=round(direct, 4), total_weight=W,
         mac_cpu_hours=[round(lo / 3600, 1), round(hi / 3600, 1)], pod_cpu_hours=[round(lo * 1.52 / 3600, 1), round(hi * 1.52 / 3600, 1)], minutes_16_shards=[round(lo * 1.52 / 16 / 60), round(hi * 1.52 / 16 / 60)],
         note='the low end is the rate on the measured small stems; the high end is dag-kit\'s rate on the 99 times the new/old CPU ratio. A stem is capped at 900 s, and the heaviest stems of the old run (b10624e5 at 655 s CPU) pass the soft end, so the last tier of a shard can run to its 900 s. Both ends are from 6 stems; refit from the first rows.')
json.dump(m, open(HERE + '/measured.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in m.items() if k != 'stems'}, indent=1))
for s in m['stems']:
    print(s)
