"""Shape of gold's form DAG, as defined in topology.md.

Usage:
  topology.py            write topology-rows.jsonl (skips finished stems) and topology-table.md
  topology.py --show STEM [STEM ...]   print the forms, depths, reads, chains, roots and widths of those stems
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ROOT = '/Users/davidlu/code/arc-workspace/'
GOLD = ROOT + 'work/lm/data-study/gold/gold-export/'
STUDY = ROOT + 'work/lm/data-study/'
sys.path.insert(0, STUDY + 'sampler/sampler-worker/sampler-ident-match-read')
from common import gold_forms  # noqa: E402

ROWS = HERE + 'topology-rows.jsonl'
TABLE = HERE + 'topology-table.md'
RAMP_JSONL = STUDY + 'gold/gold-heldout-ramp-dag/heldout-ramp.jsonl'
EVAL_TXT = STUDY + 'features-worker/arm/eval-tasks.txt'
SETS = [('eval37', 'The 37'), ('ramp', 'Ramp'), ('train', 'Training'), ('eval62', 'Other 62 eval')]


def kind_of(line):
    return re.match(r'\((\S+)', line).group(1)


def analyse(kinds, reads):
    """Graph figures for nodes 0..n-1 with reads[i] = earlier nodes that i reads."""
    n = len(kinds)
    if n == 0:
        return None
    outd, ind = [0] * n, [len(r) for r in reads]
    for i, r in enumerate(reads):
        for q in r:
            outd[q] += 1
    edges = [(q, i) for i, r in enumerate(reads) for q in r]
    depth = []
    for i, r in enumerate(reads):
        depth.append(1 + max((depth[q] for q in r), default=0))
    per = {}
    for d in depth:
        per[d] = per.get(d, 0) + 1
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    chain_edges = [(u, v) for u, v in edges if outd[u] == 1 and ind[v] == 1]
    for u, v in chain_edges:
        parent[find(u)] = find(v)
    comp = {}
    for i in range(n):
        comp.setdefault(find(i), []).append(i)
    chains = sorted((sorted(c) for c in comp.values()), key=lambda c: (-len(c), c[0]))
    lens = [len(c) for c in chains]
    pairs = {}
    for u, v in chain_edges:
        k = kinds[u] + '>' + kinds[v]
        pairs[k] = pairs.get(k, 0) + 1
    in2 = sum(1 for c in chains if len(c) >= 2 for _ in c)
    in3 = sum(1 for c in chains if len(c) >= 3 for _ in c)
    e = len(edges)
    return dict(
        n=n, e=e, depth=max(depth), width=max(per.values()), depth_over_n=max(depth) / n,
        share2=in2 / n, share3=in3 / n,
        chain_edge_share=(len(chain_edges) / e) if e else None,
        branch_share=sum(1 for x in outd if x >= 2) / n,
        join_share=sum(1 for x in ind if x >= 2) / n,
        sink_share=sum(1 for x in outd if x == 0) / n,
        n_chains2=sum(1 for x in lens if x >= 2), longest=max(lens),
        chains=lens,
        kind_pairs=pairs,
    ), chains


NBIN = 10


def thirds(depth_count):
    """Size of the first and of the last third of depths 1..D (the ceiling of D/3)."""
    return -(-depth_count // 3)


def rooted(kinds, reads, depth):
    """Figures with roots (forms that read no form) set aside, as in topology.md."""
    n = len(kinds)
    roots = [i for i in range(n) if not reads[i]]
    rs = set(roots)
    keep = [i for i in range(n) if i not in rs]
    new = {old: j for j, old in enumerate(keep)}
    r2 = [[new[q] for q in reads[i] if q in new] for i in keep]
    res = analyse([kinds[i] for i in keep], r2) if keep else None
    chains = [[keep[j] for j in c] for c in res[1]] if res else []
    pairs = {}
    if res:
        for p, c in res[0]['kind_pairs'].items():
            pairs[p] = c
    longest = chains[0] if chains else []
    ties = sum(1 for c in chains if len(c) == len(longest)) if chains else 0
    read_roots = sorted({q for i in longest for q in reads[i] if q in rs})
    d_max = max(depth)
    widths = [0] * d_max
    for d in depth:
        widths[d - 1] += 1
    tail = 0
    for w in reversed(widths):
        if w != 1:
            break
        tail += 1
    t = thirds(d_max)
    head_max, last_max = max(widths[:t]), max(widths[d_max - t:])
    bins = [[] for _ in range(NBIN)]
    for d in range(1, d_max + 1):
        pos = (d - 1) / (d_max - 1) if d_max > 1 else 0.0
        bins[min(NBIN - 1, int(pos * NBIN))].append(widths[d - 1])
    profile = []
    for b in range(NBIN):
        if bins[b]:
            profile.append(sum(bins[b]) / len(bins[b]))
        else:
            d = min(d_max, max(1, round(1 + (b + .5) / NBIN * (d_max - 1))))
            profile.append(float(widths[d - 1]))
    nr = n - len(roots)
    return dict(
        n_roots=len(roots), n_nonroot=nr, roots=roots,
        longest=len(longest) if longest else None, ties=ties, chain=longest,
        longest_share_all=len(longest) / n if longest else None,
        longest_share_nonroot=len(longest) / nr if longest else None,
        roots_read=len(read_roots), roots_read_idx=read_roots,
        depth=d_max, widths=widths, tail=tail, tail_share=tail / d_max,
        head_max=head_max, last_max=last_max, head_wider=head_max > last_max,
        tail_half=2 * tail >= d_max, profile=profile, kind_pairs=pairs,
        chains=[len(c) for c in chains],
    ), chains


def program(text):
    lines, reads, depth = gold_forms(text)
    kinds = [kind_of(l) for l in lines]
    full, fchains = analyse(kinds, reads)
    keep = [i for i, k in enumerate(kinds) if k != 'DET']
    new = {old: j for j, old in enumerate(keep)}
    r2 = [[new[q] for q in reads[i] if q in new] for i in keep]
    res = analyse([kinds[i] for i in keep], r2)
    nodet, nchains = (res if res else (None, []))
    nchains = [[keep[j] for j in c] for c in nchains]
    rt, rchains = rooted(kinds, reads, depth)
    return lines, kinds, reads, full, fchains, nodet, nchains, rt, rchains


def membership():
    ev = set(open(EVAL_TXT).read().split())
    rows = [json.loads(l) for l in open(RAMP_JSONL)]
    held = {r['task'] for r in rows if r['source'] == 'eval-37'}
    ramp = {r['task'] for r in rows if r['source'] != 'eval-37'}
    return ev, held, ramp


def set_of(stem, ev, held, ramp):
    if stem in held:
        return 'eval37', ['eval37']
    if stem in ev:
        return 'eval62', ['eval62']
    if stem in ramp:
        return 'ramp', ['ramp', 'train']
    return 'train', ['train']


def load_rows():
    done, good = {}, []
    if os.path.exists(ROWS):
        bad = False
        for l in open(ROWS):
            try:
                r = json.loads(l)
            except ValueError:
                bad = True
                continue
            done[r['stem']] = r
            good.append(l if l.endswith('\n') else l + '\n')
        if bad or (good and not open(ROWS).read().endswith('\n')):
            with open(ROWS, 'w') as f:
                f.writelines(good)
    return done


def compute():
    ev, held, ramp = membership()
    man = json.load(open(GOLD + 'manifest.json'))['stems']
    done = load_rows()
    stems = sorted(f[:-7] for f in os.listdir(GOLD + 'flat') if f.endswith('.arclog'))
    new = 0
    with open(ROWS, 'a') as out:
        for s in stems:
            if s in done:
                continue
            text = open(GOLD + 'flat/' + s + '.arclog').read()
            _, kinds, _, full, _, nodet, _, rt, _ = program(text)
            st, sets = set_of(s, ev, held, ramp)
            kc = {}
            for k in kinds:
                kc[k] = kc.get(k, 0) + 1
            row = dict(stem=s, set=st, sets=sets, approximated='approximated' in man[s],
                       kinds=kc, full=full, nodet=nodet, rooted=rt)
            out.write(json.dumps(row) + '\n')
            out.flush()
            done[s] = row
            new += 1
    print('rows: %d total, %d new' % (len(done), new))
    return done


# ---- table

def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def f(x):
    return '-' if x is None else ('%.2f' % x).rstrip('0').rstrip('.')


def mq(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return '-'
    return '%s (%s to %s)' % (f(pct(xs, .5)), f(pct(xs, .25)), f(pct(xs, .75)))


FIG = [
    ('Programs in figure', None),
    ('Forms', 'n'), ('Edges', 'e'), ('Depth (forms)', 'depth'), ('Greatest forms at one depth', 'width'),
    ('Depth over forms', 'depth_over_n'),
    ('Share of forms in chains of length 2 or more', 'share2'),
    ('Share of forms in chains of length 3 or more', 'share3'),
    ('Share of edges that are chain edges', 'chain_edge_share'),
    ('Share of forms that are branches', 'branch_share'),
    ('Share of forms that are joins', 'join_share'),
    ('Share of forms that are sinks', 'sink_share'),
    ('Chains of length 2 or more per program', 'n_chains2'),
    ('Longest chain per program', 'longest'),
]
BINS = [('1', 1, 1), ('2', 2, 2), ('3', 3, 3), ('4', 4, 4), ('5 to 7', 5, 7), ('8 or more', 8, 10 ** 9)]


def table(rows, variant, title):
    out = ['## ' + title, '']
    byset = {k: [r for r in rows.values() if k in r['sets']] for k, _ in SETS}
    hdr = '| Figure | ' + ' | '.join('%s (%d)' % (name, len(byset[k])) for k, name in SETS) + ' |'
    sep = '|---|' + '---|' * len(SETS)
    out += ['Median over programs (25th to 75th percentile).', '', hdr, sep]
    for label, key in FIG:
        cells = []
        for k, _ in SETS:
            ds = [r[variant] for r in byset[k] if r[variant]]
            if key is None:
                cells.append(str(len(ds)))
            else:
                cells.append(mq([d[key] for d in ds]))
        out.append('| %s | %s |' % (label, ' | '.join(cells)))
    out += ['', 'Chains over all programs of the set: count of chains, and share of forms in them.', '',
            '| Chain length | ' + ' | '.join(name for _, name in SETS) + ' |', sep]
    stats = {}
    for k, _ in SETS:
        cnt = [0] * len(BINS)
        forms = [0] * len(BINS)
        tot = 0
        for r in byset[k]:
            d = r[variant]
            if not d:
                continue
            tot += d['n']
            for L in d['chains']:
                for b, (_, lo, hi) in enumerate(BINS):
                    if lo <= L <= hi:
                        cnt[b] += 1
                        forms[b] += L
        stats[k] = (cnt, forms, tot)
    for b, (name, _, _) in enumerate(BINS):
        cells = []
        for k, _ in SETS:
            cnt, forms, tot = stats[k]
            cells.append('%d chains, %s of forms' % (cnt[b], '%.3f' % (forms[b] / tot) if tot else '-'))
        out.append('| %s | %s |' % (name, ' | '.join(cells)))
    out += ['', 'Kind pairs (u kind > v kind) on chain edges, count over the set.', '',
            '| Pair | ' + ' | '.join(name for _, name in SETS) + ' |', sep]
    pairs = {}
    for k, _ in SETS:
        for r in byset[k]:
            d = r[variant]
            if d:
                for p, c in d['kind_pairs'].items():
                    pairs.setdefault(p, {}).setdefault(k, 0)
                    pairs[p][k] += c
    for p in sorted(pairs, key=lambda p: -sum(pairs[p].values())):
        out.append('| %s | %s |' % (p.replace('>', ' to '), ' | '.join(str(pairs[p].get(k, 0)) for k, _ in SETS)))
    out.append('')
    return out


RFIG = [
    ('Roots', 'n_roots'), ('Forms that are not roots', 'n_nonroot'),
    ('Longest chain, in forms', 'longest'),
    ('Longest chain, share of all forms', 'longest_share_all'),
    ('Longest chain, share of non-root forms', 'longest_share_nonroot'),
    ('Distinct roots read by the longest chain', 'roots_read'),
    ('Depth (forms)', 'depth'),
    ('Tail: consecutive depths of width 1 from the deepest', 'tail'),
    ('Tail, share of depth', 'tail_share'),
    ('Head: greatest width in the first third of depths', 'head_max'),
    ('Last third: greatest width in the last third of depths', 'last_max'),
]


def rooted_table(rows):
    byset = {k: [r['rooted'] for r in rows.values() if k in r['sets']] for k, _ in SETS}
    hdr = '| Figure | ' + ' | '.join('%s (%d)' % (name, len(byset[k])) for k, name in SETS) + ' |'
    sep = '|---|' + '---|' * len(SETS)
    nz = {k: [q for q in byset[k] if q['n_nonroot']] for k, _ in SETS}
    out = ['## Chains with roots set aside', '',
           'Roots (forms that read no form) and their edges are taken out; chains are found on the forms left. '
           'The longest chain is the first of the longest by form index; ties are counted below. '
           'Depth and width are of the whole program. With D depths, a third is the first or last ceiling(D/3) depths. '
           'Programs with no form left after the roots are out (%s) are left out of the longest chain figures.' % ', '.join(
               '%s %d' % (name, len(byset[k]) - len(nz[k])) for k, name in SETS),
           '', 'Median over programs (25th to 75th percentile).', '', hdr, sep]
    for label, key in RFIG:
        pool = nz if key.startswith(('longest', 'roots_read')) else byset
        out.append('| %s | %s |' % (label, ' | '.join(mq([q[key] for q in pool[k]]) for k, _ in SETS)))
    out += ['', 'Shares of programs.', '', hdr, sep]
    for label, key in [('Head wider than the last third', 'head_wider'), ('Tail at least half of the depth', 'tail_half')]:
        out.append('| %s | %s |' % (label, ' | '.join(
            '%.3f' % (sum(1 for q in byset[k] if q[key]) / len(byset[k])) for k, _ in SETS)))
    out.append('| More than one longest chain | %s |' % ' | '.join(
        '%.3f' % (sum(1 for q in nz[k] if q['ties'] > 1) / len(nz[k])) for k, _ in SETS))
    out += ['', 'Width profile: the width at each tenth of depth, with depth scaled to 0 to 1 per program. '
            'A program\'s width in a tenth is the mean width of its depths in that tenth; '
            'when none falls in it, the width at the nearest depth to its middle.', '',
            hdr, sep]
    for b in range(NBIN):
        out.append('| %s to %s | %s |' % (f(b / NBIN), f((b + 1) / NBIN),
                   ' | '.join(mq([q['profile'][b] for q in byset[k]]) for k, _ in SETS)))
    out += ['', 'Kind pairs (u kind > v kind) on chain edges after the roots are out, count over the set.', '',
            '| Pair | ' + ' | '.join(name for _, name in SETS) + ' |', sep]
    pairs = {}
    for k, _ in SETS:
        for q in byset[k]:
            for p, c in q['kind_pairs'].items():
                pairs.setdefault(p, {}).setdefault(k, 0)
                pairs[p][k] += c
    for p in sorted(pairs, key=lambda p: -sum(pairs[p].values())):
        out.append('| %s | %s |' % (p.replace('>', ' to '), ' | '.join(str(pairs[p].get(k, 0)) for k, _ in SETS)))
    out.append('')
    return out


def write_table(rows):
    ex = [r for r in rows.values() if r['nodet'] is None]
    nz = [r for r in rows.values() if r['full']['e'] == 0]
    out = ['# Shape of gold form DAG: figures', '',
           'Made by `topology.py` from `topology-rows.jsonl`. Definitions are in `topology.md`.', '',
           'The Ramp is part of Training. Approximated stems stay in: %s.' % ', '.join(
               '%s %d' % (name, sum(1 for r in rows.values() if k in r['sets'] and r['approximated'])) for k, name in SETS),
           'Programs with no edge are left out of the median of the chain-edge share (full: %d; without DET: %d).' % (
               len(nz), sum(1 for r in rows.values() if r['nodet'] and r['nodet']['e'] == 0)),
           'Programs of only DET forms have no form once DET is taken out and are left out of the second part (%d).' % len(ex),
           '']
    out += table(rows, 'full', 'All forms')
    out += table(rows, 'nodet', 'Without DET forms')
    out += rooted_table(rows)
    open(TABLE, 'w').write('\n'.join(out) + '\n')
    print('wrote', TABLE)


def depth_of(text):
    return gold_forms(text)[2]


def show(stem):
    text = open(GOLD + 'flat/' + stem + '.arclog').read()
    lines, kinds, reads, full, fchains, nodet, nchains, rt, rchains = program(text)
    print('==', stem)
    dep = depth_of(text)
    for i, l in enumerate(lines):
        print('%2d %-5s d%-2d reads %s | %s' % (i, kinds[i], dep[i], reads[i], l[:110]))
    print('full chains  :', [c for c in fchains])
    print('full figures :', json.dumps({k: v for k, v in full.items()}))
    print('nodet chains :', nchains)
    print('nodet figures:', json.dumps(nodet))
    print('roots        :', rt['roots'])
    print('rooted chains:', rchains)
    print('longest chain:', rt['chain'], 'kinds', [kinds[i] for i in rt['chain']], 'ties', rt['ties'])
    print('roots read by longest chain:', rt['roots_read_idx'])
    print('widths by depth:', rt['widths'])
    print('tail %d (share %.3f), head max %d, last-third max %d' % (
        rt['tail'], rt['tail_share'], rt['head_max'], rt['last_max']))
    print('profile      :', [round(x, 2) for x in rt['profile']])
    print('rooted figures:', json.dumps({k: v for k, v in rt.items() if k not in ('widths', 'profile', 'roots', 'chain')}))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--show':
        for s in sys.argv[2:]:
            show(s)
    else:
        rows = compute()
        write_table(rows)
