"""Shared code of the ident block read: pins, paths, gold loaders, parse, scopes, shapes, DAG facts, gold's rates.

  ib_lib.py check     prints the pins and exits 1 on a mismatch
  ib_lib.py manifest  writes manifest.json

Design: /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-design/design.md
"""
import collections
import gc
import glob
import gzip
import hashlib
import json
import os
import random
import re
import sys
import time

R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-ident-block-read-keyident-krc-heldout37-ramp22'  # the data folder
WS = '/Users/davidlu/code/arc-workspace'
STUDY = WS + '/work/lm/data-study'
KIT = STUDY + '/sampler/sampler-worker/kits/sampler-pool-keyident-value-199853802'
SAMPLER_DIR = KIT + '/model/study/sampler'
ENGINE = STUDY + '/ast/run/runtime-0a7d32160/py313-path'
SO = ENGINE + '/arclog/arclog.abi3.so'
SO_SHA = 'b41ccf9c0567b923f04771d7b5e479172d94f30fa09e4a9b181713ec19e043a3'
VENV = STUDY + '/ast/run/runtime-kaggle-py313/venv'
PY = VENV + '/bin/python'
SAMPLER_FILES = ['live.py', 'sample2_col.py', 'search.py', 'superdag.py', 'superdag_search.py', 'live_try.py', 'or_q.py']
SAMPLER_SHA = 'a5873bf24e00'
MODELS = {'37': KIT + '/models-kr', 'ramp': KIT + '/models-krf', 'corpus': KIT + '/models-kr'}
MODEL_SHAS = {  # 16 hex digits of sha256
    'models-kr/live_priors.pkl': '3c859731e9d875ce',
    'models-kr/relR4_o.pkl': '3015d409597fff42',
    'models-kr/choice5_o.pkl': '686949ea5cc5a89f',
    'models-kr/tilt_v1.json': 'ca858276d4713e92',
    'models-krf/live_priors.pkl': '7406dc3e810f5211',
    'models-krf/relR4_o.pkl': '3015d409597fff42',
    'models-krf/choice5_o.pkl': '686949ea5cc5a89f',
    'models-krf/tilt_v1.json': 'ca858276d4713e92',
}
GOLD_DIR = STUDY + '/features-worker/results/features-node-score-refit-loop/live-gold-r1'
HELD_GOLD = GOLD_DIR + '/points-eval.json'
HELD_GOLD_SHA = 'af855438abe27a5b'
IDENT_LIST = GOLD_DIR + '/gold-ident-only-refit.json'
IDENT_LIST_SHA = '08ec1bc4d836c650'
HELD_DIR = STUDY + '/sampler/sampler-worker/held'
EVAL_TASKS = STUDY + '/features-worker/arm/eval-tasks.txt'
CORPUS_GOLD = STUDY + '/sampler/sampler-worker/sampler-view-final-2149'
CORPUS_TASKS = WS + '/data/tasks'
DESIGN = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-design/design.md'
SETTINGS_ENV = dict(P_DAG='1', ORDER_FREE='col,tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
KINDS = ('RULE', 'DET', 'INIT', 'RIGID_DET')
NAME = re.compile(r'&[A-Za-z_]\w*')
KEY_OPEN = re.compile(r'\(key\s+\(')
CARET = re.compile(r'\^[A-Za-z_]\w*')
MIN_CELL = 40
LEVELS = ['C2', 'C1', 'I2', 'I1', 'K']
LINK_BINS = ['1', '2', '3-4', '5+']

live = live_try = D = None  # loaded by setup()


# ------------------------------------------------------------------ pins

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_lines(path):
    return [x.strip() for x in open(path) if x.strip()]


def held_tasks():
    return read_lines(HELD_DIR + '/tasks.txt')


def ramp_tasks():
    return read_lines(HELD_DIR + '/ramp-fold.txt')


def set_of(task):
    if task in held_tasks():
        return '37'
    if task in ramp_tasks():
        return 'ramp'
    return 'corpus'


def corpus_stems():
    """All stems of the corpus copy, less the 99 eval tasks, less the 22 ramp tasks."""
    skip = set(read_lines(EVAL_TASKS)) | set(ramp_tasks())
    return sorted(s for s in os.listdir(CORPUS_GOLD) if os.path.exists('%s/%s/pairs.jsonl.gz' % (CORPUS_GOLD, s)) and s not in skip)


def corpus_gold(stem):
    with gzip.open('%s/%s/pairs.jsonl.gz' % (CORPUS_GOLD, stem), 'rt') as f:
        return json.loads(f.readline())['gold_sexp']


def corpus_pin():
    stems = corpus_stems()
    lines = ['%s\t%s' % (s, hashlib.sha256(corpus_gold(s).encode()).hexdigest()) for s in stems]
    return dict(stems=len(stems), sha256=hashlib.sha256('\n'.join(sorted(lines)).encode()).hexdigest(), source=CORPUS_GOLD,
                excluded=dict(eval_tasks=EVAL_TASKS, ramp=HELD_DIR + '/ramp-fold.txt'))


def pins():
    """[(name, ok, value)]"""
    out = []

    def add(name, ok, value):
        out.append((name, bool(ok), value))
    h = hashlib.sha256()
    for f in SAMPLER_FILES:
        h.update(open(SAMPLER_DIR + '/' + f, 'rb').read())
    add('sampler code', h.hexdigest().startswith(SAMPLER_SHA), h.hexdigest()[:12])
    add('engine arclog.abi3.so', sha256(SO) == SO_SHA, sha256(SO)[:12])
    add('python', sys.version.startswith('3.13') and os.path.realpath(sys.prefix) == os.path.realpath(VENV), '%s %s' % (sys.version.split()[0], sys.prefix))
    for k, v in MODEL_SHAS.items():
        got = sha256(KIT + '/' + k)[:16]
        add(k, got == v, got)
    add('held gold', sha256(HELD_GOLD).startswith(HELD_GOLD_SHA), sha256(HELD_GOLD)[:12])
    add('ident-only list', sha256(IDENT_LIST).startswith(IDENT_LIST_SHA), sha256(IDENT_LIST)[:12])
    add('task sets', (len(held_tasks()), len(ramp_tasks())) == (37, 22), (len(held_tasks()), len(ramp_tasks())))
    stems = corpus_stems()
    add('corpus stems', len(stems) == 989, len(stems))
    pf = R + '/corpus-pin.json'
    if os.path.exists(pf):
        got, want = corpus_pin(), json.load(open(pf))
        add('corpus pin', got['stems'] == want['stems'] and got['sha256'] == want['sha256'], got['sha256'][:12])
    env = {k: os.environ.get(k) for k in SETTINGS_ENV}
    add('settings env', env == SETTINGS_ENV and 'STEER_COVER' not in os.environ, env)
    return out


def check_pins(verbose=False):
    bad = [p for p in pins() if not p[1]]
    if verbose:
        for name, ok, value in pins():
            print('%-4s %-28s %s' % ('ok' if ok else 'BAD', name, value))
    if bad:
        print('pin mismatch: ' + ', '.join('%s=%s' % (n, v) for n, _, v in bad), file=sys.stderr)
        sys.exit(1)


def setup():
    """Checks the pins, puts the sampler and the engine first on sys.path and imports the sampler modules."""
    global live, live_try, D
    check_pins()
    sys.dont_write_bytecode = True
    sys.path[:0] = [SAMPLER_DIR, ENGINE]
    import live as _live
    import live_try as _live_try
    import superdag as _D
    live, live_try, D = _live, _live_try, _D
    assert os.path.dirname(_live.arclog.__file__) == os.path.dirname(SO), _live.arclog.__file__
    return live, live_try, D


# ------------------------------------------------------------------ gold

def held_gold():
    return {x['task']: x['gold_sexp'] for x in json.load(open(HELD_GOLD))}


def ident_list():
    return json.load(open(IDENT_LIST))


def forms_of(text):
    return [f for f in text.split('\n') if f.strip() and not f.startswith('(OUT')]


def parse(form):
    words = form.split()
    w0 = words[0].lstrip('(')
    return dict(kind=w0 if w0 in KINDS else 'OTHER', head=words[1].rstrip(')'), names=set(NAME.findall(form)))


def ancestors(g, reads):
    seen, todo = set(), list(reads[g])
    while todo:
        j = todo.pop()
        if j not in seen:
            seen.add(j)
            todo += reads[j]
    return seen


def valid_order(scope, reads, rng):
    """A random topological order of the scope (a set of form indices), drawn from rng."""
    left, order = set(scope), []
    while left:
        ready = sorted(j for j in left if not (set(reads[j]) & left))
        if not ready:
            raise ValueError('cycle in scope')
        j = rng.choice(ready)
        order.append(j)
        left.discard(j)
    return order


def session_of(path):
    """An open-world session of the task with no test output, as live_try.session_of makes it, and the task dict."""
    d = json.load(open(path))
    for t in d['test']:
        t.pop('output', None)
    sess = live.arclog.Session(live.arclog.Task.from_json(json.dumps(d), live.arclog.World.Open), live.arclog.DecodeSettings(**live_try.SETTINGS), session_bytes=2 << 30)
    return sess, d


def task_path(task, st=None):
    st = st or set_of(task)
    return ('%s/data/tasks/%s.json' % (KIT, task)) if st in ('37', 'ramp') else ('%s/%s.json' % (CORPUS_TASKS, task))


def replay(sampler, d, sess, forms, seconds=120):
    """([step_tables result per form replayed], error or None) of the forms, as a program in this order."""
    gc.collect()  # live.Sampler sets gc thresholds so high that a finished Run keeps its decoders; a few of them leave the session with empty tables
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + seconds, d, live.Limits())
    run.collect = []
    err = None
    try:
        run.scope(forms)
    except Exception as e:  # noqa: BLE001
        err = '%s: %s' % (type(e).__name__, str(e)[:120])
    got = run.collect
    del run
    gc.collect()
    return got, err


# ------------------------------------------------------------------ shapes

def tabs_of(ct):
    return [[str(t) for t in D.OneTable(ct, j).tables['column_types'][0]] for _, j in D.relation_tables(ct)]


def has_ident(tab):
    return sum('Ident' in t for t in tab)


def key_clause(text):
    m = KEY_OPEN.search(text)
    if not m:
        return None
    depth = 0
    for j in range(m.start(), len(text)):
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                return text[m.start():j + 1]
    return text[m.start():]


def shape_tabs(kind, text, tabs):
    """'kind|I|K'. Reads the text for the key clause and the tables for column types."""
    if not tabs:
        i = 'none'
    else:
        c = min(has_ident(t) for t in tabs)
        i = '3+' if c >= 3 else str(c)
    k = '-'
    if kind == 'INIT':
        kc = key_clause(text)
        if kc is None:
            k = 'nokey'
        else:
            nk = len(set(CARET.findall(kc)))
            k = 'key-ident' if tabs and has_ident(tabs[0][:nk]) else 'key-plain'
    return '%s|%s|%s' % (kind, i, k)


def shape_of(kind, text, ct):
    return shape_tabs(kind, text, tabs_of(ct))


def within(shape):
    return shape.split('|', 1)[1]


def i_ge1(shape):
    return within(shape).split('|')[0] in ('1', '2', '3+')


# ------------------------------------------------------------------ DAG facts

def bin_nscope(n):
    return '0' if n == 0 else '1-2' if n <= 2 else '3-5' if n <= 5 else '6-11' if n <= 11 else '12+'


def bin_ident_in(n):
    return '0' if n == 0 else '1' if n == 1 else '2-3' if n <= 3 else '4+'


def bin_link_in(n):
    return '0' if n == 0 else '1' if n == 1 else '2' if n == 2 else '3-4' if n <= 4 else '5+'


def link_bin(n):
    return '1' if n <= 1 else '2' if n == 2 else '3-4' if n <= 4 else '5+'


def analyze(forms, cts):
    """One dict per form that has its tables and all its ancestors' tables: i, head, kind, shape, tabs, holds, ident_only, link, scope,
    nscope, facts. cts is the replay's step_tables results in the order of forms (it may be shorter). Reads only the read edges and the tables."""
    n, have = len(forms), len(cts)
    P = [parse(f) for f in forms]
    at = {}
    for i, p in enumerate(P):
        at.setdefault(p['head'], i)
    reads = [sorted({at[x] for x in p['names'] if x in at} - {i}) for i, p in enumerate(P)]
    tabs = [tabs_of(ct) for ct in cts] + [None] * (n - have)
    holds = [t is not None and any(has_ident(tb) for tb in t) for t in tabs]
    link = {}

    def link_of(i, seen=()):
        if i in link:
            return link[i]
        if i in seen:
            raise ValueError('cycle')
        if not holds[i]:
            link[i] = 0
        else:
            link[i] = 1 + max([link_of(j, seen + (i,)) for j in reads[i] if holds[j]], default=0)
        return link[i]
    out = []
    for i in range(n):
        try:
            anc = ancestors(i, reads)
        except RecursionError:
            continue
        if i >= have or any(j >= have for j in anc) or i in anc:
            continue
        for j in anc | {i}:
            link_of(j)
        read_by = {j for k in anc for j in reads[k] if j in anc}
        sinks = [j for j in anc if j not in read_by]
        facts = dict(nscope=bin_nscope(len(anc)), ident_in=bin_ident_in(sum(holds[j] for j in anc)), ident_sink=int(any(holds[j] for j in sinks)),
                     link_in=bin_link_in(max([link[j] for j in anc], default=0)))
        shape = shape_tabs(P[i]['kind'], forms[i], tabs[i])
        out.append(dict(i=i, head=P[i]['head'], kind=P[i]['kind'], shape=shape, tabs=tabs[i], holds=holds[i], ident_only=bool(tabs[i]) and all(has_ident(tb) for tb in tabs[i]),
                        link=link[i], scope=sorted(anc), nscope=len(anc), facts=facts))
    return out, reads


def cell(facts, level):
    f = facts
    if level == 'C2':
        return (f['nscope'], f['ident_in'], f['ident_sink'], f['link_in'])
    if level == 'C1':
        return (f['nscope'], f['ident_in'], f['ident_sink'])
    if level == 'I2':
        return (f['ident_in'], f['ident_sink'])
    if level == 'I1':
        return (f['ident_in'] != '0', f['ident_sink'])
    return ()


def scope_class(facts):
    """The three scope classes of the response table."""
    if facts['ident_in'] == '0':
        return 'no Ident in scope'
    return 'Ident at a sink' if facts['ident_sink'] else 'Ident in scope, not at a sink'


class Gold:
    """Gold's rates from corpus rows: p(shape | cell) = (count + .5) / (count in cell + .5 V), with the backoff of the design."""

    def __init__(self, rows):
        self.n = len(rows)
        self.shape_n = {lv: collections.defaultdict(collections.Counter) for lv in LEVELS}
        self.kind_n = {lv: collections.defaultdict(collections.Counter) for lv in LEVELS}
        for r in rows:
            k = r['shape'].split('|')[0]
            for lv in LEVELS:
                c = cell(r['facts'], lv)
                self.shape_n[lv][c][r['shape']] += 1
                self.kind_n[lv][c][k] += 1
        self.V = max(1, len({r['shape'] for r in rows}))
        self.Vk = max(1, len({r['shape'].split('|')[0] for r in rows}))
        self.total = {lv: {c: sum(v.values()) for c, v in self.shape_n[lv].items()} for lv in LEVELS}

    def level_of(self, facts, start='C1'):
        for lv in LEVELS[LEVELS.index(start):]:
            if lv == 'K' or self.total[lv].get(cell(facts, lv), 0) >= MIN_CELL:
                return lv

    def rate(self, shape, facts, start='C1'):
        """(p_gold of the shape, level used, forms in that cell)"""
        lv = self.level_of(facts, start)
        c = cell(facts, lv)
        tot = self.total[lv].get(c, 0)
        return (self.shape_n[lv][c][shape] + .5) / (tot + .5 * self.V), lv, tot

    def rate_kind(self, kind, facts, start='C1'):
        lv = self.level_of(facts, start)
        c = cell(facts, lv)
        tot = self.total[lv].get(c, 0)
        return (self.kind_n[lv][c][kind] + .5) / (tot + .5 * self.Vk)


def load_corpus(dirs=None):
    """(rows, task lines, shard_done count) from the corpus row files. A stem is counted once."""
    rows, tasks, done = [], {}, 0
    files = sorted(sum((glob.glob(d + '/rows-*.jsonl') for d in (dirs or [R + '/corpus'])), []))
    seen_rows = {}
    for fn in files:
        for line in open(fn):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get('rec') == 'task':
                tasks[x['stem']] = x
            elif x.get('rec') == 'shard_done':
                done += 1
            elif 'stem' in x:
                seen_rows.setdefault(x['stem'], []).append(x)
    for s in tasks:
        rows += seen_rows.get(s, [])
    return rows, tasks, done


def load_gold(dirs=None):
    rows, tasks, _ = load_corpus(dirs)
    return Gold(rows), rows, tasks


# ------------------------------------------------------------------ picks

def pick_pass1(task, info):
    """(Ident-only g's, plain g's) of pass 1: up to 12 Ident-only forms in strata taken in turn, up to 3 plain forms."""
    groups = collections.defaultdict(list)
    for a in info:
        if a['ident_only']:
            groups[(a['kind'], link_bin(a['link']))].append(a['i'])
    rng = random.Random('%s pass1 ident' % task)
    keys = sorted(groups)
    for k in keys:
        rng.shuffle(groups[k])
    ident = []
    while len(ident) < 12 and any(groups.values()):
        for k in keys:
            if groups[k] and len(ident) < 12:
                ident.append(groups[k].pop())
    plain = [a['i'] for a in info if a['tabs'] and not a['holds'] and a['kind'] in KINDS]
    rng2 = random.Random('%s pass1 plain' % task)
    return sorted(ident), sorted(rng2.sample(plain, min(3, len(plain))))


def pick_pass3(corpus_rows, n=60):
    """[(stem, g)] of the in-sample control: Ident-only corpus forms stratified by (kind, link bin), seeded."""
    groups = collections.defaultdict(list)
    for r in corpus_rows:
        if r['ident_only'] and r['kind'] in KINDS:
            groups[(r['kind'], link_bin(r['link']))].append((r['stem'], r['g']))
    rng = random.Random('pass3')
    keys = sorted(groups)
    for k in keys:
        groups[k].sort()
        rng.shuffle(groups[k])
    out = []
    while len(out) < n and any(groups.values()):
        for k in keys:
            if groups[k] and len(out) < n:
                out.append(groups[k].pop())
    return sorted(out)


def draw_seed(task, g, i):
    return int(hashlib.sha1(('%s %d %d' % (task, g, i)).encode()).hexdigest()[:12], 16)


def jeffreys(h, n):
    from scipy.stats import beta
    lo, hi = beta.ppf([.025, .975], h + .5, n - h + .5)
    return float(lo), float(hi)


def append_line(fh, obj):
    fh.write(json.dumps(obj, separators=(',', ':')) + '\n')
    fh.flush()


def rss_gib():
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (2 ** 30 if sys.platform == 'darwin' else 2 ** 20)


def eta(done, total, t0):
    el = time.time() - t0
    rate = el / max(done, 1)
    return rate, rate * (total - done)


# ------------------------------------------------------------------ draws

def draw_batch(sampler, sess, d, texts, kind, seeds, ident_heads, cpu_stop=None):
    """[(shape, reads an Ident scope form) or None] per seed: Sampler.clause over the scope texts. cpu_stop() true ends the batch early."""
    out = []
    for s in seeds:
        if cpu_stop is not None and cpu_stop():
            break
        c = sampler.clause(sess, s, time.monotonic() + 20, d, texts, kind)
        if c is None:
            out.append(None)
            continue
        out.append((shape_of(kind, c.text, c.tables), bool(set(NAME.findall(c.text)) & ident_heads)))
    return out


def p_kind_of(sampler, texts, kind):
    """(P_kind, admitted kinds) at the scope texts, as superdag.Pool.kind weighs them. sampler.run must exist (a clause call makes it)."""
    run = sampler.run
    run.deadline = time.monotonic() + 20
    dec, _ = run.scope(texts)
    kinds = {k: sum(c.get(k, 0) for c in sampler.pri['kinds1'].values()) for k in live.KIND_TOK}
    names = [k for k in live.KIND_TOK if dec.admits([live.KIND_TOK[k]])[0]]
    if kind not in names:
        return 0.0, names
    return (kinds[kind] + 1) / sum(kinds[k] + 1 for k in names), names


# ------------------------------------------------------------------ manifest

PREDICTIONS = [
    'A: proposal conditioning blocks. A1 on the 37 >=40% of Ident-only forms (weighted) under and median L >=2 bits; A2 plain control <=15% under and median L <=1; A3 median L at link 1 and 2 >=2; A4 proposal log-odds rise of I>=1 from no-Ident scopes to Ident-sink scopes under half of gold rise.',
    'B: compounding over depth blocks. B1 <=15% under and median L <=1; B2 slope within +-.3 bits a link and median L at link 5+ <=1.5.',
    'C: conditioning worsens with depth. Median L at link 1 and 2 <=1 and slope >=.5 bits a link.',
    'Point: INIT keyed on Ident median L 4 to 5.5 bits, >=70% under; INIT not keyed median L 0 to 1, <=15% under; RULE median L 1 to 2, 10 to 25% under; all Ident-only on the 37 median L 1.5 to 2.5, 20 to 35% under, slope 0 to +.3; verdict mixed; plain median L <=.7, <=10% under; L_kind -.5 to +.7.',
    'Table 4: INIT draw reads an Ident scope form on 25 to 35% of draws at Ident scopes; median p_prop/p_gold of keyed INIT .03 to .1.',
]


def write_manifest(extra=None):
    m = dict(
        design=DESIGN, record=R, date=time.strftime('%Y-%m-%d %H:%M:%S'),
        kit=KIT, sampler_sha_prefix=SAMPLER_SHA, engine=ENGINE, engine_so_sha256=SO_SHA, python=PY,
        models=dict(MODELS, **{'note': 'the 37 and pass 3 use models-kr, the ramp uses models-krf'}), model_sha256_prefix16=MODEL_SHAS,
        settings=SETTINGS_ENV | {'STEER_COVER': 'unset'},
        held_gold=dict(path=HELD_GOLD, sha256_prefix=HELD_GOLD_SHA), ident_only_list=dict(path=IDENT_LIST, sha256_prefix=IDENT_LIST_SHA),
        corpus_gold=dict(path=CORPUS_GOLD, pin=R + '/corpus-pin.json', stems='all less eval-tasks.txt (99) less ramp-fold.txt (22): 989'),
        task_sets=dict(held=HELD_DIR + '/tasks.txt', ramp=HELD_DIR + '/ramp-fold.txt'),
        task_json=dict(held=KIT + '/data/tasks/<task>.json', corpus=CORPUS_TASKS + '/<task>.json'),
        predictions=PREDICTIONS,
    )
    m.update(extra or {})
    json.dump(m, open(R + '/manifest.json', 'w'), indent=1)
    return m


if __name__ == '__main__':
    if sys.argv[1:] == ['check']:
        check_pins(verbose=True)
    elif sys.argv[1:] == ['manifest']:
        write_manifest()
        print('wrote', R + '/manifest.json')
    else:
        sys.exit(__doc__)
