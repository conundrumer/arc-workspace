"""Compares shape rows of the fork stage with the shape pod's rows of the same stems: landings, bits, seconds, CPU.

  python3 gold_combined_landing_compare.py ROWS.jsonl ... [--old-mac ROWS.jsonl ...] [--json OUT.json]

A stem is `same` where `program_steps`, `before`, `after`, `base_ended` and `landed` equal the pod's row. It is `old cap` where the pod's row stopped at a cap (`late` or `error`) and its `program_steps` start the new row's, so the new row went on past that cap. Any other stem is DIFF, with where the two first part. With --old-mac, the old stage's rows on this Mac add a CPU column and a compare of the pod's row against the Mac's, which tells a pod effect from a code effect.
"""
import glob, json, statistics, sys

POD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-shape-cut/pod-out/rows-*.jsonl'
KEYS = ('program_steps', 'before', 'after', 'base_ended', 'landed')


def rows_of(paths):
    got = {}
    for p in paths:
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            got[r['task']] = r
    return got


def same(a, b):
    return all(a.get(k) == b.get(k) for k in KEYS)


def prefix(o, r):
    a, b = o.get('program_steps') or [], r.get('program_steps') or []
    return b[:len(a)] == a and (o.get('late') or o.get('error')) is not None


def first_part(o, r):
    a, b = o.get('program_steps') or [], r.get('program_steps') or []
    k = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return 'steps %d vs %d, part at %d; before same %s; score %s vs %s; sum %s vs %s; cap old %s %s new %s %s; kept old %s new %s' % (len(a), len(b), k, o.get('before') == r.get('before'), (o.get('after') or {}).get('score'), (r.get('after') or {}).get('score'), (o.get('after') or {}).get('sum'), (r.get('after') or {}).get('sum'), o.get('late'), o.get('error'), r.get('late'), r.get('error'), o.get('kept_out'), r.get('kept_out'))


def main():
    args = sys.argv[1:]
    out = None
    if '--json' in args:
        k = args.index('--json')
        out = args[k + 1]
        args = args[:k] + args[k + 2:]
    macs = []
    if '--old-mac' in args:
        k = args.index('--old-mac')
        macs = args[k + 1:]
        args = args[:k]
    pod, new, mac = rows_of(glob.glob(POD)), rows_of(args), rows_of(macs)
    table, tally = [], {'same': 0, 'old cap': 0, 'DIFF': 0}
    print('stem      class    pod cpu  mac old cpu  mac new cpu  new wall  peak GiB  procs  reads  pod-prefix  new-prefix')
    for t, r in sorted(new.items(), key=lambda x: -(pod[x[0]].get('cpu') or 0)):
        o = pod[t]
        cls = 'same' if same(o, r) else 'old cap' if prefix(o, r) else 'DIFF'
        tally[cls] += 1
        m = mac.get(t)
        ot, rt = o.get('times') or {}, r.get('times') or {}
        print('%-9s %-8s %7.1f  %11s  %11.1f  %8.1f  %8s  %5s  %5s  %10.1f  %10.1f' % (t, cls, o.get('cpu') or 0, '-' if m is None else '%.1f' % (m.get('cpu') or 0), r.get('cpu') or 0, r.get('wall') or 0, r.get('peak_gib'), r.get('peak_procs'), r.get('reads'), ot.get('prefix step', 0), rt.get('prefix step', 0)))
        if cls == 'DIFF':
            print('   DIFF', first_part(o, r))
            if m is not None:
                print('   mac old against pod:', 'same' if same(o, m) else first_part(o, m))
                print('   mac old against new:', 'same' if same(m, r) else first_part(m, r))
        table.append(dict(task=t, cls=cls, pod_cpu=o.get('cpu'), mac_old_cpu=None if m is None else m.get('cpu'), mac_new_cpu=r.get('cpu'), peak_gib=r.get('peak_gib'), peak_procs=r.get('peak_procs')))
    print('stems', len(new), tally)
    both = [x for x in table if x['mac_old_cpu'] and x['mac_new_cpu']]
    if both:
        a, b = sum(x['mac_old_cpu'] for x in both), sum(x['mac_new_cpu'] for x in both)
        print('same machine, stems %d: old cpu %.1f, new cpu %.1f, ratio %.2f, median stem ratio %.2f' % (len(both), a, b, a / b, statistics.median(x['mac_old_cpu'] / x['mac_new_cpu'] for x in both)))
    a, b = sum(x['pod_cpu'] or 0 for x in table), sum(x['mac_new_cpu'] or 0 for x in table)
    print('pod cpu %.1f, Mac new cpu %.1f, ratio %.2f (two machines)' % (a, b, a / max(b, 0.1)))
    if out:
        json.dump(table, open(out, 'w'))


if __name__ == '__main__':
    main()
