"""Paths, the 13 tasks, gold parsing, and the stub unpickler for bank files."""
import glob, json, os, pickle, re

W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
H = os.path.dirname(os.path.abspath(__file__)) + '/'  # this folder: output rows, and copies of gold-dups.jsonl, gold-sig.jsonl, bits/
OLD = W + 'sampler-hour-stall-read-fold13/'  # the hour read's rows, read by seed-hour.py only
KIT = W + 'kits/sampler-pool-fold-hour-8be414670/'
HOUR = W + 'sampler-pool-fold-hour-3600s/out/'
FLAT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-pool-flat-scope-13tasks-3600s/out/'
FLAT_ARMS = ['flat600_s0', 'flat600_s1']
EXT = W + 'sampler-pool-fold-hour-ext-3600s/out/'
TASKS = '2c0b0aff 74dd1130 aa18de87 b9b7f026 d23f8c26 5b37cb25 8e2edd66 b2862040 4df5b0ae 94133066 c35c1b4c d0f5fe59 e69241bd'.split()
ARMS = ['hour_s0', 'hour_s1']
TASKDIR = '/Users/davidlu/code/arc-workspace/data/tasks/'


def gold_text():
    return {x['task']: x['gold_sexp'] for x in json.load(open(W + 'sampler-extended-cut/points-with-ramp.json'))}


class Stub:
    def __init__(self, *a, **k):
        pass

    def __setstate__(self, s):
        if isinstance(s, dict):
            self.__dict__.update(s)
        elif isinstance(s, tuple):
            for x in s:
                if isinstance(x, dict):
                    self.__dict__.update(x)


class U(pickle.Unpickler):
    def find_class(self, m, n):
        if m.startswith(('superdag', '__main__', 'policy', 'sklearn', 'numpy')) or m in ('live',):
            try:
                return super().find_class(m, n)
            except Exception:
                return type(n, (Stub,), {})
        return super().find_class(m, n)


def bank(path):
    return U(open(path, 'rb')).load()


TOK = re.compile(r'[()]|[^\s()]+')


def sexp(text):
    stack, top = [], []
    cur = top
    for t in TOK.findall(text):
        if t == '(':
            n = []
            cur.append(n)
            stack.append(cur)
            cur = n
        elif t == ')':
            cur = stack.pop()
        else:
            cur.append(t)
    return top[0]


def is_atom(x):
    if not x or not isinstance(x[0], str):
        return False
    h = x[0]
    if h.startswith(':') or h in ('OR', 'NOT', 'ALL', 'AND'):
        return False
    if h.startswith('&'):
        return True
    if h in ('!=', '<', '<=', '>', '>=', '='):
        return True
    return len(x) > 1 and isinstance(x[1], list) and bool(x[1]) and isinstance(x[1][0], str) and x[1][0].startswith(':')


def count(x):
    if not isinstance(x, list):
        return 0
    if is_atom(x):
        return 1
    return sum(count(y) for y in x)


def atoms(text):
    return count(sexp(text)[2:])


def gold_forms(text):
    """Non-OUT lines, the direct read forms of each by index, depth of each."""
    lines = [l for l in text.strip().split('\n') if not l.startswith('(OUT')]
    head, reads, depth = {}, [], []
    for i, x in enumerate(lines):
        names = re.findall(r'&r\d+', x)
        h = names[0]
        r = sorted({head[m] for m in names[1:] if m in head and m != h})
        reads.append(r)
        depth.append(1 + max((depth[q] for q in r), default=0))
        head[h] = i
    return lines, reads, depth


def read_jsonl(path):
    out = []
    for l in open(path, errors='replace'):
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def run_dir(root, arm, task):
    return '%s%s/%s/' % (root, arm, task)


def start_of(root, arm, task):
    return float(open(run_dir(root, arm, task) + 'start').read())


def visits_of(root, arm, task):
    d = run_dir(root, arm, task) + 'work/'
    vs = []
    for p in glob.glob(d + '*.visits'):
        vs += read_jsonl(p)
    vs.sort(key=lambda v: v['time'])
    return vs


SIGS = {}


def recorded_covers(root, arm, task):
    d = run_dir(root, arm, task) + 'work/'
    cs = []
    for p in glob.glob(d + '*.out.jsonl.cover'):
        cs += read_jsonl(p)
    cs.sort(key=lambda c: c['time'])
    return cs


def covers_of(root, arm, task):
    """The run's cover events, with one more event per bank node whose row hashes and column types equal a gold table. The worker's gold keys miss tables with tied columns, so a node of such a table has no event of its own. An added event takes the time of the visit that holds its draw."""
    if not SIGS:
        for r in read_jsonl(H + 'gold-sig.jsonl'):
            SIGS[r['task']] = {}
            for x in r['tables']:
                if x.get('examples') is not None:
                    SIGS[r['task']].setdefault(json.dumps([x['types'], x['examples']]), set()).add(x['form'])
    cs = recorded_covers(root, arm, task)
    seen = {(c['gold'], c['draw']) for c in cs}
    st = bank(run_dir(root, arm, task) + 'work/' + task + '.out.jsonl.bank')
    vs = visits_of(root, arm, task)
    ends, cum = [], 0
    for v in vs:
        cum += v['tries']
        ends.append(cum)
    import bisect
    for n in st['nodes'].values():
        for g in SIGS[task].get(json.dumps([sorted(n.table_types), n.examples]), ()):
            if (g, n.age) not in seen:
                seen.add((g, n.age))
                i = min(bisect.bisect_left(ends, n.age), len(vs) - 1)
                cs.append(dict(gold=g, depth=n.depth, draw=n.age, time=vs[i]['time'], added=1))
    cs.sort(key=lambda c: c['time'])
    return cs
