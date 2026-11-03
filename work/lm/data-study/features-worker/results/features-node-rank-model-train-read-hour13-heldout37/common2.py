"""Shared paths, the two record sets, the draw clock, table ids, gold labels and the machine line.

Import as `C2`. It imports flat_common.py (this folder) as `C`.
Runs on PY = /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python -I (numpy 2.5.4, Python 3.12).
"""
import bisect, collections, glob, importlib.util, json, os, re, sys

POOLG = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, POOLG)
import flat_common as C
W = C.W
ROWS = POOLG + 'rows/'
BASE_ROOT = W + 'sampler-pool-extended-text-pass1-600s/out-all37/'
BASE_TASKS = open(W + 'held/tasks.txt').read().split()
KIT_BASE = W + 'kits/sampler-pool-extended-text-pass1-8be414670/'
KIT_HOUR = W + 'kits/sampler-pool-fold-hour-8be414670/'
GOLD_HOUR = C.gold_text()
GOLD_BASE = {x['task']: x['gold_sexp'] for x in json.load(open(KIT_BASE + 'points-eval.json'))}

class LazyGold(dict):
    """{task: gold_sexp} of N600, read from the combined cut's view-final when first asked."""
    def __missing__(self, t):
        import gzip
        x = json.loads(gzip.open(C.W + '../../gold/gold-v3-combined-cut/view-final/%s/pairs.jsonl.gz' % t, 'rt').readline())['gold_sexp']
        self[t] = x
        return x


# One row per record set. `cuts` are seconds on the task's start-file clock.
SETS = {
    'hour': dict(root=C.HOUR, arms=['hour_s0', 'hour_s1'], tasks=C.TASKS, cuts=[600, 3600], gold=GOLD_HOUR, sig=C.H + 'gold-sig.jsonl', dups=C.H + 'gold-dups.jsonl',
                 row='Hour: sampler-pool-fold-hour-3600s/out, arms hour_s0 hour_s1, 13 tasks, cuts 600 s and 3600 s, gold-v3-extended-cut sampler-extended-cut/points-with-ramp.json sha256 dabccbe1, '
                     'runs on one pod EPYC 9654 wheel c87cf482a, models-coverf'),
    'base': dict(root=BASE_ROOT, arms=['base_s0', 'base_s1'], tasks=BASE_TASKS, cuts=[600], gold=GOLD_BASE, sig=POOLG + 'gold-sig37.jsonl', dups=POOLG + 'gold-dups37.jsonl',
                 row='Base: sampler-pool-extended-text-pass1-600s/out-all37, arms base_s0 base_s1, 37 tasks (held/tasks.txt), cut 600 s, gold-v3-extended-cut/view-pass1/points-eval.json sha256 d3460f46, '
                     'runs on 8 pods EPYC 9654 (two hosts at load 24-38 and 240-275) wheel c87cf482a, models-base'),
}
SETS['n600'] = dict(root=W + 'sampler-pool-dag-nodes-train50-600s/out/', arms=['nodes_s0'], tasks=open(POOLG + 'n600-tasks.txt').read().split(), cuts=[600], gold=LazyGold(), sig=POOLG + 'gold-sig-n600.jsonl',
                    dups=POOLG + 'gold-dups-n600.jsonl', row='N600: sampler-pool-dag-nodes-train50-600s/out, arm nodes_s0, 50 tasks, cut 600 s, gold-v3-cuts-final-round52 view-final; a tune set, not held; dups file is empty (no aliases)')
MACHINE = 'read on the Mac (Darwin 24.6.0 arm64, Python 3.12, numpy 2.5.4), row hashes from runtime ba0754492'


def meta(which, extra=''):
    """The header line of every printed table: the record set's row, and the read's machine."""
    return '[%s; %s%s]' % (SETS[which]['row'], MACHINE, ('; ' + extra) if extra else '')


class ClockError(Exception):
    pass


def log_blocks(path):
    """[[after-load node count, end draws or None]] per `generation ` line of a log, in order."""
    blocks = []
    for l in open(path, errors='replace'):
        if l.startswith('generation '):
            m = re.search(r'after load, (\d+) forms, (\d+) nodes', l)
            blocks.append([int(m[2]) if m else None, None])
        elif l.startswith('end: ') and blocks:
            m = re.match(r'end: \w+, (\d+) draws', l)
            if m:
                blocks[-1][1] = int(m[1])
    return blocks


def clock(root, arm, task):
    """The draw clock of a run. Returns dict(visits, lost, dead, blocks, base). Each kept visit has d0, d1, t (seconds on the start file clock), block.
    Raises ClockError where a check of the design fails."""
    base = C.start_of(root, arm, task)
    vs = C.visits_of(root, arm, task)
    path = C.run_dir(root, arm, task) + 'work/' + task + '.log'
    lb = log_blocks(path)
    blk, prev = -1, -1.0
    for v in vs:
        if v['seconds'] < prev or blk < 0:
            blk += 1
        prev = v['seconds']
        v['block'] = blk
    nb = blk + 1
    if nb != len(lb):
        raise ClockError('%s %s: %d visit blocks, %d log blocks' % (arm, task, nb, len(lb)))
    dead = []
    for i, (after, end) in enumerate(lb):
        if end is None and i < len(lb) - 1:
            if lb[i + 1][0] != after:
                raise ClockError('%s %s: block %d has no end line and the next block loads %s nodes, not %s' % (arm, task, i, lb[i + 1][0], after))
            dead.append(i)
    keep = [v for v in vs if v['block'] not in dead]
    lost = sum(v['tries'] for v in vs if v['block'] in dead)
    cum = 0
    last = {}
    for v in keep:
        v['d0'], cum = cum, cum + v['tries']
        v['d1'] = cum
        v['t'] = v['time'] - base
        last[v['block']] = v
    for i, (after, end) in enumerate(lb):
        if end is not None and i in last and last[i]['d1'] != end:
            raise ClockError('%s %s: block %d last visit ends at draw %d, the end line says %d' % (arm, task, i, last[i]['d1'], end))
    return dict(visits=keep, lost=lost, dead=dead, blocks=lb, base=base)


def draw_at(clk, t, st_draws):
    """(d(t), second of that visit): d1 of the last visit with t <= the second, at most the bank's draws."""
    vs = clk['visits']
    ts = [v['t'] for v in vs]
    j = bisect.bisect_right(ts, t) - 1
    if j < 0:
        return 0, 0.0
    return min(vs[j]['d1'], st_draws), vs[j]['t']


def draw_at_end(clk, st_draws):
    """(the draw of the last bank write, the second of the visit that holds it)."""
    vs = clk['visits']
    ends = [v['d1'] for v in vs]
    j = min(bisect.bisect_left(ends, st_draws), len(vs) - 1)
    return st_draws, vs[j]['t']


def table_ids(nodes):
    """({node id: table id}, [table pair]) by the pair json.dumps([sorted(table_types), examples]), ids in node order."""
    ids, pairs, out = {}, [], {}
    for n in sorted(nodes):
        s = json.dumps([sorted(nodes[n].table_types), nodes[n].examples])
        if s not in ids:
            ids[s] = len(pairs)
            pairs.append(s)
        out[n] = ids[s]
    return out, pairs


def sig_table(which, task):
    """{pair string: set of gold forms}, and {gold form: set of pair strings} from the gold signatures of a task."""
    by_pair, by_form = collections.defaultdict(set), collections.defaultdict(set)
    for r in C.read_jsonl(SETS[which]['sig']):
        if r['task'] != task:
            continue
        for x in r['tables']:
            if x.get('examples') is not None:
                s = json.dumps([x['types'], x['examples']])
                by_pair[s].add(x['form'])
                by_form[x['form']].add(s)
    return by_pair, by_form


def covers(which, arm, task, st):
    """Cover events of a run: recorded, and added by row hash for each node whose table equals a gold table (as common.covers_of, with this record set's signatures).
    The time of an added event isn't set: the draw is right and the read uses draws."""
    by_pair, _ = sig_table(which, task)
    cs = C.recorded_covers(SETS[which]['root'], arm, task)
    seen = {(c['gold'], c['draw']) for c in cs}
    for n in st['nodes'].values():
        for g in by_pair.get(json.dumps([sorted(n.table_types), n.examples]), ()):
            if (g, n.age) not in seen:
                seen.add((g, n.age))
                cs.append(dict(gold=g, depth=n.depth, draw=n.age, added=1))
    return cs


def labels(which, task, cs):
    """Gold labels of a run. Returns dict(lines, reads, kinds, first, tables, readers, nokey):
    first[g]: least draw of the cover events of g (the least over aliases, for a form with no table of its own), or None;
    tables[g]: set of table pair strings of gold form g (the alias tables, for a form with no table of its own);
    readers[q]: gold forms that read q, OUT lines dropped."""
    lines, reads, depth = C.gold_forms(SETS[which]['gold'][task])
    dups = {json.loads(l)['task']: json.loads(l) for l in open(SETS[which]['dups'])}[task]
    nokey = set(dups['no_key'])
    alias = {int(i): v for i, v in dups['alias'].items()}
    first = {}
    for c in cs:
        g = c['gold']
        first[g] = min(first.get(g, 1 << 60), c['draw'])
    _, tabs = sig_table(which, task)
    f2, t2 = {}, {}
    for g in range(len(lines)):
        if g in nokey:
            xs = [first[a] for a in alias[g] if a in first]
            f2[g] = min(xs) if xs else None
            t2[g] = set().union(*[tabs[a] for a in alias[g]]) if alias[g] else set()
        else:
            f2[g] = first.get(g)
            t2[g] = set(tabs[g])
    kinds = [x[1:x.index(' ')] for x in lines]
    readers = collections.defaultdict(list)
    for h, rs in enumerate(reads):
        for q in rs:
            readers[q].append(h)
    return dict(lines=lines, reads=reads, kinds=kinds, first=f2, tables=t2, readers=readers, nokey=nokey, depth=depth)
