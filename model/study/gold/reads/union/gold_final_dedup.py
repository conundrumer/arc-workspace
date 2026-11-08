"""Equal tables on the final text: finds each gold form of view-final whose tables equal an earlier form's tables in the same program on every case, and cuts the later form where the trial passes the bar and ranks lower. design.md in work/lm/data-study/gold/gold-v3-combined-cut/dedup-final/ gives the definitions. Rows in rows.jsonl in that folder; a stem with no pair has a row in no_pair.jsonl, so a restart skips it.

  <runtime python> gold_final_dedup.py run
  <runtime python> gold_final_dedup.py child STEM...
  <runtime python> gold_final_dedup.py pairs STEM...    prints the equal pairs of each stem, with no trial
"""
import collections, glob, gzip, hashlib, itertools, json, os, re, sys, time
import gold_cheapest_prune as P
from gold_cheapest_prune import C, holds, name_of, program_lines
C.GIB = 4  # a stem past 4 GiB is set aside; 6 shards share the machine

CUT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut'  # the folder of the data: view-final/ and dedup-final/ (the rows and the design)
DEDUP = CUT + '/dedup-final'
VIEW = CUT + '/view-final/'
OUT = DEDUP + '/rows.jsonl'
NONE = DEDUP + '/no_pair.jsonl'
LIB = str(P.ROOT / 'docs/arclog/lib.md')
RAMP = P.D + 'sampler/sampler-worker/held/ramp-fold.txt'
TRIES = 5000  # column matchings tried for one pair of relations


def text_of(t):
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def vsha(text):
    return hashlib.sha256('\n'.join(text.splitlines()).encode()).hexdigest()[:16]


def outputs():
    """{component: [(output name, [its column names without key])]} from the lib doc, in the order of the doc."""
    got, cur = {}, None
    for l in open(LIB):
        m = re.match(r'- \*\*(\w+)\*\*', l)
        if m:
            cur = got.setdefault(m[1], [])
            continue
        m = re.match(r'\s+- out `(\w+)\(([^)]*)\)`', l)
        if m and cur is not None:
            cur.append((m[1], [c.split(':')[0].strip() for c in m[2].split(',') if c.split(':')[0].strip() != 'key']))
    return got


OUTS = outputs()


class Tab:
    """One relation's table: labels, types, widths, and per entry its example, its DET assignment and its rows."""

    def __init__(self, tb):
        self.labels, self.types, self.widths = list(tb['labels']), [str(x) for x in tb['types']], list(tb['widths'])
        self.at = [sum(self.widths[:k]) for k in range(len(self.widths) + 1)]
        self.ents = [(tuple(e[0]), {s: v[0] for s, v in e[1].items()}, sorted(e[2])) for e in tb['entries']]
        self.col = [[hash(tuple(sorted(r[self.at[c]:self.at[c + 1]] for r in rows))) for c in range(len(self.widths))] for _, _, rows in self.ents]

    def keys(self, canon):
        """{(example, assignment with its DET slots canonical): entry index}, or None where two entries share a key."""
        got = {(ex, frozenset((canon.get(s, s), rows) for s, rows in asg.items())): i for i, (ex, asg, _) in enumerate(self.ents)}
        return got if len(got) == len(self.ents) else None


def matches(g, f, kg, kf, by_label):
    """The columns of f that stand for g's under some matching with the same rows on every entry, or None. by_label: matched columns share a label."""
    if kg is None or kf is None or kg.keys() != kf.keys() or len(g.widths) != len(f.widths):
        return None
    order = list(kg)
    gi, fi = [kg[k] for k in order], [kf[k] for k in order]
    if any(len(g.ents[a][2]) != len(f.ents[b][2]) for a, b in zip(gi, fi)):
        return None
    n = len(g.widths)
    gs = [(g.labels[c] if by_label else None, g.types[c], g.widths[c], tuple(g.col[a][c] for a in gi)) for c in range(n)]
    fs = [(f.labels[c] if by_label else None, f.types[c], f.widths[c], tuple(f.col[a][c] for a in fi)) for c in range(n)]
    if sorted(map(repr, gs)) != sorted(map(repr, fs)):
        return None
    groups = collections.defaultdict(lambda: ([], []))
    for c in range(n):
        groups[gs[c]][0].append(c)
        groups[fs[c]][1].append(c)
    keys = list(groups)
    for combo in itertools.islice(itertools.product(*[itertools.permutations(groups[k][1]) for k in keys]), TRIES):
        pi = [0] * n
        for k, perm in zip(keys, combo):
            for c, d in zip(groups[k][0], perm):
                pi[c] = d
        if all(sorted(g.ents[a][2]) == sorted(tuple(x for c in range(n) for x in r[f.at[pi[c]]:f.at[pi[c] + 1]]) for r in f.ents[b][2]) for a, b in zip(gi, fi)):
            return pi
    return None


def form_tables(bar, text):
    """({form: {slot: (Tab, column names)}}, {form: reason}): the tables of each form of the text, read at the step that ends the form, on every case."""
    sess = bar.session()
    a, b = bar.stream(sess, text)
    toks = [t for t, k in zip(a, b) if k]
    end = max((i for i, t in enumerate(toks) if t == P.live.OUT_TOK), default=len(toks))
    d, ct, got, bad = sess.decoder(), None, {}, {}
    for t in toks[:end]:
        d.step(t)
        ct = P.arclog.step_tables(d, *P.live.TABLES, False, ct)
        for s, j in P.DAG.relation_tables(ct):
            f = int(ct.tables['form'][j])
            try:
                got.setdefault(f, {})[s] = (Tab(P.DAG.S.parse_table(P.DAG.OneTable(ct, j))), list(ct.tables['column_names'][j]))
            except Exception as e:  # noqa: BLE001
                bad[f] = 'table unread: %s %s' % (type(e).__name__, str(e)[:100])
    return got, bad


def relations(line, tabs):
    """{name: Tab} of the relations that the form of line defines, or the reason it has none to compare."""
    kind = line.split()[0][1:]
    if kind != 'INIT':
        return ({'': next(iter(tabs.values()))[0]}, None) if len(tabs) == 1 else (None, '%d tables' % len(tabs))
    comp = line.split()[2]
    if comp not in OUTS:
        return None, 'component %s not in the lib' % comp
    m = re.match(r'\(INIT &r(\d+) ', line)
    base = int(m[1]) if m else min(tabs)
    got = {}
    for s, (tab, names) in tabs.items():
        if 0 <= s - base < len(OUTS[comp]):
            name, cols = OUTS[comp][s - base]
            seen = [x for x in (re.sub(r'\.c\d+$', '', x) for x in names) if x != 'key']  # a column of several cells has the name `a.c0`, `a.c1`, ...
            seen = [x for k, x in enumerate(seen) if k == 0 or x != seen[k - 1]]
            if seen != cols[len(cols) - len(seen):]:
                return None, 'output %s of %s has columns %s, not %s' % (name, comp, names, cols)
            got[name] = tab
    return (got, None) if got else (None, 'no output table')


def find_pairs(bar, lines):
    """(pairs, unread): each pair g, f with f earlier whose tables are equal, as `equal_pairs` of the design gives them, and {form: reason} for forms that have no tables to compare."""
    forms = [x for x in lines if not x.startswith('(OUT')]
    tabs, unread = form_tables(bar, '\n'.join(lines))
    rel, canon, pairs = {}, {}, []
    for g, line in enumerate(forms):
        if g in unread or g not in tabs:
            unread.setdefault(g, 'no table')
            continue
        got, why = relations(line, tabs[g])
        if why:
            unread[g] = why
            continue
        kind, comp = line.split()[0][1:], line.split()[2] if line.startswith('(INIT') else None
        first = None
        for f in range(g):
            if f not in rel or rel[f][0] != kind or rel[f][1] != comp or not set(got) <= set(rel[f][2]):
                continue
            canon_g = dict(canon)
            if kind == 'DET':
                canon_g[next(iter(tabs[g]))] = canon.get(next(iter(tabs[f])), next(iter(tabs[f])))
            classes = []
            for name, tab in got.items():
                other = rel[f][2][name]
                kg, kf = tab.keys(canon_g), other.keys(canon)
                classes.append('equal' if matches(tab, other, kg, kf, True) is not None else 'equal under relabelling' if matches(tab, other, kg, kf, False) is not None else None)
            if None not in classes:
                pairs.append(dict(g=g, f=f, kinds=[kind, kind], component=comp, labels=[name_of(line), name_of(forms[f])], eq='equal' if set(classes) == {'equal'} else 'equal under relabelling'))
                first = f if first is None else first
        if kind == 'DET' and first is not None:
            sg, sf = next(iter(tabs[g])), next(iter(tabs[first]))
            canon[sg] = canon.get(sf, sf)
        rel[g] = (kind, comp, got)
    return pairs, unread


def rename(lines, g, f):
    """lines without the form labelled g, and each read of g in the others on f."""
    return [re.sub(re.escape(g) + r'(?=[ .)])', f, x) for x in lines if name_of(x) != g]


def say(f0, f1):
    return 'worst %.2f to %.2f, sum %.2f to %.2f, undrawable %d to %d' % (f0['worst'], f1['worst'], f0['sum'], f1['sum'], len(f0['undrawable']), len(f1['undrawable']))


def one(t, bits):
    print('stem', t, flush=True)
    text = text_of(t)
    row = dict(stem=t, vsha=vsha(text))
    bar = P.Bar(t)
    ls = program_lines(text)
    pairs, unread = find_pairs(bar, ls)
    if not pairs:
        return dict(row, pairs=[], taken=None, why='no equal pair', unread=len(unread))
    row.update(pairs=pairs, verdicts=[], unread=unread)
    cut = sorted((p for p in pairs if p['eq'] == 'equal'), key=lambda p: (-p['g'], p['f']))
    if not cut:
        return dict(row, taken=None, why='%d pairs, all under relabelling' % len(pairs))
    try:
        gold = bar.walk(ls)
    except Exception as e:  # noqa: BLE001
        return dict(row, taken=None, why='rows unread: ' + str(e)[:120])
    if not gold[1]:
        return dict(row, taken=None, why='the text does not end')
    before = bits.whole(t, ls)
    row['before'] = before
    now, cur, norm, out, dropped = list(ls), before, None, set(), []
    for p in cut:
        lg, lf = p['labels']
        v = dict(g=p['g'], f=p['f'])
        row['verdicts'].append(v)
        if lg in out:
            v['verdict'] = 'g is out already'
            continue
        trial = rename(now, lg, lf)
        why, n = holds(bar, trial, gold)
        if why:
            v['verdict'] = why
            continue
        fig = bits.whole(t, program_lines(n))
        if P.rank(fig) >= P.rank(cur):
            v['verdict'] = 'not cheaper on rank: ' + say(cur, fig)
            continue
        v['verdict'] = 'stands: ' + say(cur, fig)
        now, cur, norm = trial, fig, n
        out.add(lg)
        dropped.append([p['g'], p['f']])
    if not dropped:
        return dict(row, taken=None, why='%d pairs tried, none stands' % len(cut))
    return dict(row, taken=True, dropped=dropped, program=norm, after=cur, why='%d of %d pairs stand: %s' % (len(dropped), len(cut), say(before, cur)))


def child(stems):
    bits = P.Bits()
    for t in stems:
        print(json.dumps(one(t, bits)), flush=True)


class Rows:
    """The file the watchdog writes to: a stem with a pair or a set_aside goes to rows.jsonl, any other to no_pair.jsonl."""

    def __init__(self, rows, none):
        self.rows, self.none = rows, none

    def write(self, line):
        r = json.loads(line)
        if r.get('set_aside'):
            self.rows.write(json.dumps(dict(r, vsha=vsha(text_of(r['stem'])))) + '\n')
        elif r.get('pairs'):
            self.rows.write(line)
        else:
            self.none.write(json.dumps(dict(stem=r['stem'], vsha=r['vsha'])) + '\n')

    def flush(self):
        self.rows.flush()
        self.none.flush()


def order():
    have = set(os.listdir(VIEW))
    ramp = open(RAMP).read().split()
    first = [t for t in P.HELD + ramp if t in have]
    first = list(dict.fromkeys(first))
    return first + sorted(t for t in have if t not in first and os.path.exists(VIEW + t + '/pairs.jsonl.gz'))


def run(args=()):
    """`run K N` takes the stems at positions K, K + N, ... of the order and writes rows-K.jsonl and no_pair-K.jsonl."""
    k, n = (int(args[0]), int(args[1])) if args else (0, 1)
    out_p, none_p = (OUT, NONE) if n == 1 else (DEDUP + '/rows-%d.jsonl' % k, DEDUP + '/no_pair-%d.jsonl' % k)
    done = set()
    for p in glob.glob(DEDUP + '/rows*.jsonl') + glob.glob(DEDUP + '/no_pair*.jsonl'):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                done.add((r['stem'], r.get('vsha')))
    left = [t for i, t in enumerate(order()) if i % n == k and (t, vsha(text_of(t))) not in done]
    print(len(left), 'stems', flush=True)
    with open(out_p, 'a', buffering=1) as rows, open(none_p, 'a', buffering=1) as none:
        out = Rows(rows, none)
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


def show(stems):
    for t in stems:
        t0 = time.time()
        pairs, unread = find_pairs(P.Bar(t), program_lines(text_of(t)))
        print(t, 'seconds', round(time.time() - t0, 1), 'unread', unread)
        for p in pairs:
            print('  g%d = g%d  %s  %s  %s' % (p['g'], p['f'], p['kinds'][0] + (' ' + p['component'] if p['component'] else ''), p['labels'], p['eq']))


if __name__ == '__main__':
    {'child': child, 'pairs': show}.get(sys.argv[1], run)(sys.argv[2:])
