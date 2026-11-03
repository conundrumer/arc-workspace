"""Per-depth reach of union tables in round 1's bundle jobs, seed 0 against seed 1000, at 600 s, and seeds a per-depth test needs.

Input: work/lm/data-study/gold/gold-union/reach-SET.jsonl (written by gold_union_reach.py), field `per`:
{depth: {tables, reached, ...}} per (task, job, seconds). Jobs 'r1 bundle_s0' and 'r1 bundle_s1', seconds 600.
Bands: work/measures.md lines 348 and 349.
Streams each file. Exits 75 when RSS passes 3 GiB.
"""
import hashlib, json, math, os, resource, sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
LIMIT = 3 * 1024 ** 3
ZA, ZB = 1.959964, 0.841621
BAND = {
    'ramp': {0: 2, 1: 8, 2: 5, 3: 3, 4: 0, 5: 1, 6: 1, 'deeper': 0},
    '37': {0: 6, 1: 7, 2: 2, 3: 2, 4: 2, 5: 1, 6: 2, 9: 1, 11: 1, 12: 1, 15: 1, 16: 7},
}
TABLES_MEASURES = {'ramp': [79, 59, 52, 47, 53, 48, 39, 68], '37': [123, 78, 74, 85, 83, 98, 88, 723]}


def guard():
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss > LIMIT:
        sys.exit(75)


def sha16(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def load(s):
    per = {}
    with open(G + 'reach-%s.jsonl' % s) as f:
        for line in f:
            if '"r1 bundle_s' not in line:
                continue
            e = json.loads(line)
            if e['seconds'] != 600 or e['job'] not in ('r1 bundle_s0', 'r1 bundle_s1') or e.get('soak_time'):
                continue
            per[e['task'], e['job'][-1]] = {int(d): (v['tables'], v['reached']) for d, v in e['per'].items()}
            guard()
    return per


def main():
    for s in ('ramp', '37'):
        print('== set', s, 'graph-tables sha256[:16]', sha16(G + 'graph-tables-%s.jsonl' % s))
        per = load(s)
        tasks = sorted({t for t, _ in per})
        both = [t for t in tasks if (t, '0') in per and (t, '1') in per]
        print('tasks with both seeds', len(both), 'of', len(tasks))
        depths = sorted({d for t in both for d in per[t, '0']} | {d for t in both for d in per[t, '1']})
        rows = {}
        for d in depths:
            T = R0 = R1 = V = A = 0
            mism = 0
            for t in both:
                a = per[t, '0'].get(d, (0, 0))
                b = per[t, '1'].get(d, (0, 0))
                if a[0] != b[0]:
                    mism += 1
                T += a[0]
                R0 += a[1]
                R1 += b[1]
                x = b[1] - a[1]
                V += x * x
                A += abs(x)
            rows[d] = (T, R0, R1, R1 - R0, V, A, mism)
        print('depth | union tables | reached s0 | reached s1 | s1-s0 | sum of squared per-task differences | sum of abs per-task differences | tasks whose table counts differ')
        for d in depths:
            print(d, '|', ' | '.join(str(x) for x in rows[d]))
        deep = [d for d in depths if d >= 7]
        print('tables 0..6 and 7+:', [rows[d][0] if d in rows else 0 for d in range(7)], sum(rows[d][0] for d in deep), 'measures:', TABLES_MEASURES[s])
        print('seeds per depth: depth | band | T=max(band+1,2) | sigma_pair (r1) | sigma_band=band/1.96 | M | mean-test seeds (r1 sigma) | mean-test seeds (band sigma) | rule power at 2 seeds (r1 sigma) | (band sigma) | rule false-move rate at M=0 (r1) | (band)')
        bd = BAND[s]
        keys = list(range(7)) + ([7] if s == 'ramp' else sorted(set(deep) | {k for k in bd if isinstance(k, int) and k >= 7}))
        for d in keys:
            if s == 'ramp' and d == 7:
                V = sum(rows[x][4] for x in deep)
                B = bd['deeper']
                label = '7+'
            else:
                V = rows[d][4] if d in rows else 0
                B = bd.get(d, 0)
                label = str(d)
            T = max(B + 1, 2)
            for M in (3, 5, 10):
                out = [label, B, T]
                sig_r, sig_b = math.sqrt(V), B / 1.96
                out += ['%.2f' % sig_r, '%.2f' % sig_b, M]
                for sg in (sig_r, sig_b):
                    out.append(max(2, math.ceil((ZA + ZB) ** 2 * sg * sg / (M * M))) if sg > 0 else 2)
                for sg in (sig_r, sig_b):
                    p = (1.0 if M >= T else 0.0) if sg == 0 else phi((M - (T - 0.5)) / sg)
                    out.append('%.3f' % (p * p))
                for sg in (sig_r, sig_b):
                    p0 = 0.0 if sg == 0 else phi(-(T - 0.5) / sg)
                    out.append('%.4f' % (2 * p0 * p0))
                print(' | '.join(str(x) for x in out))
    print('max RSS MiB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 2 ** 20)


if __name__ == '__main__':
    main()
