"""Code that the hand rewrite, case choice and prune steps of revision gold-v3-cheapest-round50 share: the bar of gold_helper_one.py for any stem, the census read of a form in the all-earlier-forms context with its cache, and the move of crossing clauses and cover candidates onto another text.

The cache is round-out/cheapest-bits.jsonl, keyed as census_bands_cheapest.py keys forms.jsonl: the task and the hash of the program up to and including the form. forms.jsonl is read at the start, so a form it holds is not read again.
"""
import glob, gzip, hashlib, json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path

os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import arclog, live, or_q, superdag as DAG
import search_gold as SG

ROOT = Path('/Users/davidlu/code/arc-workspace')
D = str(ROOT / 'work/lm/data-study') + '/'
HERE = D + 'gold/gold-v3-cover-forms-a036da074/'
HELP = D + 'gold/gold-v3-helper-forms-a036da074/'
GEN = D + 'gold/gen-v3-11f6a212c/'
BANDS_FORMS = D + 'census/census-bands-cheapest/forms.jsonl'
HELD = open(D + 'sampler/sampler-worker/held/tasks.txt').read().split()
EVAL = open(D + 'features-worker/arm/eval-tasks.txt').read().split()
CACHE = HERE + 'round-out/cheapest-bits.jsonl'
CAP = 300
NAME = re.compile(r'&[A-Za-z_0-9]+')
guided = or_q.GuidedRun
or_q.GuidedRun = lambda pri, sess, deadline, tj, lim: guided(pri, sess, deadline + CAP - 120, tj, lim)  # the walk's own deadline matches the cap, as in census_bands_cheapest.py


def masked(x):
    return NAME.sub('&_', x)


def program_lines(text):
    return [x for x in text.splitlines() if x.strip()]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def key_of(task, lines, i):
    return hashlib.sha256(('%s\n' % task + '\n'.join(lines[:i + 1])).encode()).hexdigest()[:20]


def first_row(path):
    with gzip.open(path, 'rt') as f:
        return json.loads(f.readline())


def view_row(t):
    """The first row of the stem in the view, or None where the view has no folder."""
    p = HERE + 'corpus-view/%s/pairs.jsonl.gz' % t
    return first_row(p) if os.path.exists(p) else None


class Bar:
    """The bar of gold_helper_one.py on one stem."""

    def __init__(self, task):
        self.task = task
        self.text = (ROOT / 'data/tasks' / f'{task}.json').read_text()

    def session(self):
        return arclog.Session(arclog.Task.from_json(self.text, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))

    @staticmethod
    def stream(sess, text):
        i, m, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
        return [int(x) for x in i], [int(bool(x)) for x in m]

    def walk(self, ls):
        """The OUT rows of the program ls by example, whether it ended, and its attempts."""
        out = next(x for x in ls if x.startswith('(OUT'))
        names = re.findall(r'\^(\w+)', out)
        body = re.sub(r'\^(\w+)', r'(:\1 *\1)', out[5:-1])
        body = re.sub(r'\(:(\w+) \(:\w+ \*(\w+)\)\)', r'(:\1 *\2)', body)
        added = '(RULE &zz_out %s)' % body
        probe = '(OUT (&zz_out %s))' % ' '.join('^' + n for n in names)
        sess = self.session()
        a, b = self.stream(sess, '\n'.join([x for x in ls if x is not out] + [added, probe]))
        toks = [t for t, k in zip(a, b) if k]
        d = sess.decoder()
        i = max(j for j, t in enumerate(toks) if t == live.OUT_TOK)
        ct = None
        for t in toks[:i]:
            d.step(t)
            ct = arclog.step_tables(d, *live.TABLES, True, ct)
        tb = [DAG.S.parse_table(DAG.OneTable(ct, j)) for _, j in DAG.relation_tables(ct)][-1]
        for t in toks[i:]:
            d.step(t)
        start = [sum(tb['widths'][:k]) for k in range(len(tb['widths']))]
        cols = sorted(range(len(start)), key=tb['labels'].__getitem__)
        by_label = lambda r: tuple(x for k in cols for x in r[start[k]:start[k] + tb['widths'][k]])
        return {str(tuple(e[0])): sorted(str(by_label(r)) for r in e[2]) for e in tb['entries']}, bool(d.ended), d.attempts()

    def direct(self, text):
        """Steps the program text as it stands: whether it ended, and its attempts."""
        sess = self.session()
        a, b = self.stream(sess, text)
        d = sess.decoder()
        for t, k in zip(a, b):
            if k:
                d.step(t)
        return bool(d.ended), d.attempts()

    def normal(self, text):
        """The normal form of the text, and whether it is a fixed point of the round trip."""
        sess = self.session()
        norm = arclog.StudyProgram.from_stream(sess, *self.stream(sess, text)).sexp()
        return norm, arclog.StudyProgram.from_stream(sess, *self.stream(sess, norm)).sexp() == norm


class Bits:
    """Census reads in the all-earlier-forms context, each kept in the cache file."""

    def __init__(self, log=True):
        self.rows, self.sampler = {}, None
        for p in (BANDS_FORMS, CACHE):
            if os.path.exists(p):
                for l in open(p):
                    try:
                        r = json.loads(l)
                    except json.JSONDecodeError:
                        continue
                    if r.get('status') in ('ok', 'no bits'):
                        self.rows[r['task'], r['key']] = dict(bits=r.get('bits'), why=r.get('why') or (str(r.get('bad'))[:120] if r.get('bad') else r.get('dead')))
        self.out = open(CACHE, 'a') if log else None

    def read(self, task, ctx):
        """The row of the last form of ctx, in the context of the forms before it."""
        i = len(ctx) - 1
        k = task, key_of(task, ctx, i)
        if k in self.rows:
            return self.rows[k]
        head = ctx[i].split()[0][1:]
        row = dict(bits=None, why=None)
        if head not in live.KIND_TOK:
            row['why'] = 'a %s form: no draw makes this kind' % head
        else:
            if self.sampler is None:
                self.sampler = live.Sampler(SG.MODELS, tuple(live.STEERS))
            SG.gold_of = lambda t, c_, p, x=ctx: (t, x)
            try:
                q = or_q.one(self.sampler, task, head, [i, 0], head)
            except Exception as e:  # noqa: BLE001
                row['why'] = '%s: %s' % (type(e).__name__, str(e)[:200])
            else:
                if not q.get('bad') and q.get('dead') is None and q.get('total') is not None and not q.get('left'):
                    row['bits'] = q['total']
                else:
                    row['why'] = str(q.get('bad') or q.get('dead') or q.get('left'))[:200]
        self.rows[k] = row
        self.out.write(json.dumps(dict(task=task, key=k[1], status='ok' if row['bits'] is not None else 'no bits', **row)) + '\n')
        self.out.flush()
        return row

    def whole(self, task, ls, tick=None):
        """The figures of the program's forms: sum and worst of the forms with bits, and undrawable, the lines of the others with the reason."""
        total, bad, worst = 0.0, [], 0.0
        for i, x in enumerate(ls):
            if x.startswith('(OUT'):
                continue
            if tick:
                tick()
            r = self.read(task, ls[:i + 1])
            if r['bits'] is None:
                bad.append(dict(line=i, why=r['why']))
            else:
                total += r['bits']
                worst = max(worst, r['bits'])
        return dict(sum=round(total, 2), worst=round(worst, 2), undrawable=bad)


def rank(f):
    """Lower is cheaper: fewer undrawable forms, then the lower worst form, then the lower sum."""
    return len(f['undrawable']), f['worst'], f['sum']


def crossing_read(t):
    """The stem's clauses of the latest helper census that lists it, each with the text of its clause. The text is the text the census read."""
    now = json.load(open(HERE + 'current-text.json'))[t]['lines']
    files = [(HELP + 'crossing.json', HELP + 'lines.json')]
    for f in sorted(glob.glob(HELP + 'round-out/crossing-*.json'), key=os.path.getmtime):
        files.append((f, f.replace('crossing-', 'lines-')))
    for cross, read in reversed(files):
        got = json.load(open(cross))
        if t in got:
            text = json.load(open(read)).get(t, now) if os.path.exists(read) else now
            return [dict(c, clause=text[c['line']]) for c in got[t] if c['line'] < len(text)]
    return []


def place_of(old, lines):
    """{line of old: line of lines}, pairing forms with the same text once relation names are masked, in order."""
    free = {}
    for k, x in enumerate(lines):
        free.setdefault(masked(x), []).append(k)
    return {i: free[masked(x)].pop(0) for i, x in enumerate(old) if free.get(masked(x))}


def crossing_on(t, lines):
    """The stem's crossing clauses that stand in lines, on their lines there."""
    out = []
    clauses = crossing_read(t)
    place = place_of([c['clause'] for c in clauses], lines)
    for i, c in enumerate(clauses):
        if i in place:
            out.append({k: v for k, v in dict(c, line=place[i]).items() if k != 'clause'})
    return sorted(out, key=lambda c: c['line'])


def covers_on(cands, old, lines):
    """The candidates on lines: gold_cover_round.py's `moved`."""
    place = place_of(old, lines)
    heads = {NAME.search(x)[0]: i for i, x in enumerate(old) if NAME.search(x)}
    names = {n: NAME.search(lines[place[i]])[0] for n, i in heads.items() if i in place}
    out = []
    for c in cands:
        reads = {n for f in c['forms'] for n in NAME.findall(f)}
        if c['line'] in place and not any(n in heads and n not in names for n in reads):
            out.append(dict(c, line=place[c['line']], forms=[NAME.sub(lambda m: names.get(m[0], m[0]), f) for f in c['forms']]))
    return out


def stem_covers(t, lines):
    """The stem's cover candidates on lines. They were made on lines.json text."""
    base, covers = json.load(open(HERE + 'lines.json')), json.load(open(HERE + 'covers.json'))
    return covers_on(covers.get(t, []), base.get(t, []), lines) if t in covers else []


def rss_gib(pid):
    """The process's memory in GiB: on macOS its footprint from top, which counts compressed pages that RSS leaves out; else its RSS."""
    try:
        if sys.platform == 'darwin':
            m = re.match(r'([\d.]+)([BKMG])', subprocess.check_output(['top', '-l', '1', '-pid', str(pid), '-stats', 'mem'], text=True).split()[-1])
            return float(m[1]) * {'B': 1 / (1 << 30), 'K': 1 / (1 << 20), 'M': 1 / 1024, 'G': 1}[m[2]] if m else 0
        return int(subprocess.check_output(['ps', '-o', 'rss=', '-p', str(pid)]).strip() or 0) / (1 << 20)
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 0


def finish(t, lines, seconds=900, gib=8):
    """Runs gold_cover_one.py on the program lines with the stem's crossing clauses and cover candidates on it. Returns its row, with `crossing` and `covers`, or a row with `error`. A stem with neither has no run."""
    cross, cands = crossing_on(t, lines), stem_covers(t, lines)
    info = dict(crossing=cross, covers=cands)
    if not cross and not cands:
        return dict(task=t, program='\n'.join(lines), swapped=[], cuts=[], plain=True, **info)
    with tempfile.TemporaryDirectory(dir=HERE + 'round-out') as tmp:
        ps = []
        for name, value in (('lines', {t: lines}), ('crossing', {t: cross}), ('covers', {t: cands})):
            ps.append('%s/%s.json' % (tmp, name))
            json.dump(value, open(ps[-1], 'w'))
        p = subprocess.Popen([sys.executable, '-u', HERE + 'gold_cover_one.py', t, *ps], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True, cwd=HERE)
        t0, killed = time.time(), None
        while p.poll() is None and killed is None:
            time.sleep(1)
            killed = 'time' if time.time() - t0 > seconds else 'memory' if rss_gib(p.pid) > gib else None
        if killed:
            os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
    rows = [l for l in out.splitlines() if l.startswith('{"task"')]
    row = dict(task=t, error=killed) if killed else json.loads(rows[-1]) if rows else dict(task=t, error='no row, exit %s: %s' % (p.returncode, err[-200:]))
    row.update(info)
    return row
