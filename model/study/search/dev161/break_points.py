"""break_points.py RUN ARM OUT [--tasks T,T|@FILE] [--seed N] [--shard K/N] [--limit N] [--productions union|skeleton] [--cut FILE] [--summary-only]

For each gold table of the union graph that a finished job of RUN and ARM did not reach, the class of where its path broke
(read-rule.md of the gold-break-points run, "Classes"). The output lines give each class by its code:
  1  inputs not reached (a gold table it reads was not reached; counted at the earlier depth)
  2  OUT not found (the goal table, every gold table of its program reached)
  3  writer rank: at the first state that held its inputs, the bits b of its canonical path under the served learned model exceed log2 of the job's sampled queries
  4  budget: b is within log2 of the job's sampled queries but above log2 of the queries sampled from that state on
  5  not sampled by chance: the rest
  x  not scored (no gold text, a state or a path the engine cannot step; the reason is in the job's output line)
  0  reached
Classes 3 to 5 also get the gold token of lowest rank on the path (the largest rank number), its rank, and the writing point's kind and phase.
The summary gives each class by its name.

A job is finished where RUN/results.jsonl names it for ARM and its file of sampled queries exists. One line per job streams to OUT (a zstd stream, OUT.zst),
and a job whose line is there is skipped, so a rerun takes the jobs that landed since. With --shard K/N the file is OUT-shardKofN.
The summary (always printed at the end; alone with --summary-only) reads OUT and every OUT-shard* file.

Run with the study runtime python:  PY -I break_points.py RUN ARM OUT
The code, the engine build, the learned model, the models folder, the plan and the experimental condition's extra env come from the last line of RUN/runs.jsonl.
Override: --code --site --tree --models.
The bits need WRITER_TOKEN_ID_NO_TABLE=1 (and WRITER_NO_AUTHORED=1 where the run's learned model wants it): --env NAME=VALUE, repeatable; both default to the values below.

Definitions that the rule leaves open:
- Inputs of a gold table: each query of its union tables reads union keys (union-dev.jsonl `reads`); a read of key k is reached where any graph table of k is reached; the table's inputs are reached where some such query has every read reached.
- Goal table: graph-tables `goal`. The report's kind OUT is the goal table.
- The state of a sampled query is its steps less that query. The first state that held the inputs of a production is the first sampled query whose state's tables include the production's input tables.
  d is that sampled query's number, and the queries sampled from that state on are D - d + 1.
- Productions (--productions union, the default): a production of a graph table is a union table among its `members`, one for each QueryHash. Its text is the text of its form of least length.
  Its inputs are the graph tables of the tables that the form reads: the form is the union's, its `reads` name the union tables, and the identity of the form (content, labels dropped) decides which label of the text
  names which read (Gold.producers); an output name after a label ("&r1.cell") picks the member "key.name". The labels of the text are then written as the labels of the state's queries, so no label of the union reaches the walk.
  No row store and no skeleton is read. --productions skeleton takes the queries that give the table from the skeleton, as before.
- A table can have several productions (union tables, or with --productions skeleton the skeleton's queries, that give it). Up to --max-productions of them are scored, in the order of d and then text length; the table takes the class of the most favourable (5 over 4 over 3), and its lowest b.
- Chances are writer.options' ids and writer.probabilities, as serving takes them, without the search's repeat filter. A writing point with one id costs 0 bits. A gold token that is no id, or a writing point with no id left, is b = inf.
- Ident-column tables (--flags) are counted apart: the summary's main tables leave them out.
"""
import argparse
import collections
import dataclasses
import hashlib
import itertools
import json
import math
import os
import re
import sys
import time
import zlib
from pathlib import Path

REPO = Path('/Users/davidlu/code/arc-workspace')
sys.path.insert(0, str(REPO / 'model/study'))
sys.path.insert(0, str(REPO / 'model/study/search/dev161'))
import draw_file  # noqa: E402
import reach as R  # noqa: E402
import study_zst as Z  # noqa: E402

DEV161 = REPO / 'work/lm/data-study/search/dev161'
HERE = Path(__file__).resolve().parent
SKELETON = REPO / 'work/lm/data-study/samples/dev/skeleton'
DEFAULT_ENV = ['WRITER_TOKEN_ID_NO_TABLE=1']
BANDS = ('0', '1', '2-3', '4+')
CLASSES = ('0', '1', '2', '3', '4', '5', 'x')
CLASS_NAMES = {'1': 'inputs not reached', '2': 'OUT not found', '3': 'writer rank', '4': 'budget', '5': 'not sampled by chance', 'x': 'not scored'}
CLASS_COLUMNS = ('1', '2', '3', '4', '5', 'x')
NAME = re.compile(r'&f(\d+)')
OWN = re.compile(r'^\((\w+) &f(\d+)')
FORM_HEAD = re.compile(r'\((\w+) &([A-Za-z_]\w*)')  # a union form's text: its kind and its own label
FORM_REF = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')  # a label in a union form's text, and the output name that follows it


def band(d):
    return '0' if d == 0 else '1' if d == 1 else '2-3' if d <= 3 else '4+'


# ---------------------------------------------------------------- gold

def set_files(folder, name, set_name):
    """The logical names of the files of a union folder that give `name` ('union', 'graph-tables') of the set: NAME-SET.jsonl where it exists, else the shards NAME-SET-K.jsonl
    (gold_union_graph.py SET K N writes those). Each is plain or zstd."""
    whole = str(Path(folder) / ('%s-%s.jsonl' % (name, set_name)))
    return [whole] if Z.exists(whole) else Z.glob(str(Path(folder) / ('%s-%s-[0-9]*.jsonl' % (name, set_name))))


def form_ident(text, producer):
    """The content identity of a union form (gold_union.forms_of): its text with each read replaced by the identity of the form that it reads, labels dropped.
    `producer` is {label: identity}; a label with none is written `&_`."""
    m = FORM_HEAD.match(text)
    body = text[m.end():]
    out = m[1] + FORM_REF.sub(lambda n: '{%s}%s' % (producer[n[1]], n[2]) if producer.get(n[1]) else '&_' + n[2], body)
    return hashlib.sha256(' '.join(out.split()).encode()).hexdigest()[:16]


def assignments(labels, options, need):
    """The tuples that give each label (in order) one of its options (a union key, or None), with every key of `need` given to some label."""
    def go(i, used, acc):
        if len(need - used) > len(labels) - i:
            return
        if i == len(labels):
            yield tuple(acc)
            return
        for k in options[i]:
            acc.append(k)
            yield from go(i + 1, used | {k} if k is not None else used, acc)
            acc.pop()
    yield from go(0, frozenset(), [])


class Gold:
    """The graph tables of each task, with their forms' reads, and the productions of each from the union and its graph or from the skeleton."""

    def __init__(self, union, skeleton, set_name='dev'):
        union = Path(union)
        self.skeleton = Path(skeleton)
        skip = {json.loads(l)['task'] for l in open(union / 'out-of-scope.jsonl')} if (union / 'out-of-scope.jsonl').exists() else set()
        self.tables = collections.defaultdict(dict)  # task -> graph table -> row
        for p in set_files(union, 'graph-tables', set_name):
            for r in map(json.loads, Z.open_text(p)):
                if r.get('table', '').startswith('t') and r.get('kind') != 'DEMONSTRATED' and r['task'] not in skip:
                    self.tables[r['task']][r['table']] = dict(depth=r['depth'], kind=r['kind'], goal=bool(r['goal']), members=r['members'], tables=r['tables'])
        self.union = {}  # task -> key (str) -> dict(query, kind, forms [(ident, text)], reads {ident: [key str]})
        for p in set_files(union, 'union', set_name) + [x for x in [str(union / ('union-%s-addendum.jsonl' % set_name))] if Z.exists(x)]:  # a later row of a task replaces an earlier
            for r in map(json.loads, Z.open_text(p)):
                if r['task'] in self.tables:
                    self.union[r['task']] = {str(t['key']): dict(query=t.get('query'), kind=t.get('kind'), forms=[(f['ident'], f['text']) for f in t.get('forms', ())],
                                                                 reads={i: [str(k) for k in v] for i, v in t['reads'].items()}) for t in r['tables']}
        self._sk = {}
        self._made = {}  # task -> union key -> Production or None

    def key2g(self, task):
        out = collections.defaultdict(set)
        for g, r in self.tables[task].items():
            for m in r['members']:
                out[m.split('.')[0]].add(g)
        return out

    def alternatives(self, task, g):
        """The read sets (lists of union keys) of the forms of the table's union tables."""
        u, alts = self.union.get(task, {}), []
        for m in self.tables[task][g]['members']:
            t = u.get(m.split('.')[0])
            if t:
                alts += list(t['reads'].values())
        return alts or [[]]

    def queries(self, task):
        """{QueryHash: skeleton query record} and {graph table: [QueryHash]} of the task."""
        if task not in self._sk:
            q = {}
            p = self.skeleton / (task + '.jsonl')
            if p.exists():
                for l in open(p):
                    if l.startswith('{"record": "query"'):
                        r = json.loads(l)
                        q[r['hash']] = r
            by_g = collections.defaultdict(list)
            for h, r in q.items():
                for n, g in r['graph_tables'].items():
                    by_g[g].append(h)
            self._sk = {task: (q, by_g)}
        return self._sk[task]

    def member2g(self, task):
        """{union name of a table ('key' or 'key.name'): graph table} of the task."""
        return {m: g for g, r in self.tables[task].items() for m in r['members']}

    def producers(self, task, key, ident, text):
        """{label: union key of the table that the label names in this form's text, or None} for the form `ident` of union table `key`, or None where no assignment of
        producers gives the form's content identity back. A label's producer is one of the tables that the form reads (`reads`), and the labels name all of them; a label
        with an output name after it ("&r1.cell") names an INIT or RIGID_DET table, one with none names another. Among the assignments that keep to that, the identity
        decides (form_ident): no label is believed on its own, and a label of the text need not be the own label of the form that it names, as the union keeps one text
        for each identity, and the labels are those of its first program."""
        u = self.union[task]
        body = text[FORM_HEAD.match(text).end():]
        suffixed = {}
        for n in FORM_REF.finditer(body):
            suffixed[n[1]] = suffixed.get(n[1], False) or bool(n[2])
        labels = sorted(suffixed)
        reads = u[key]['reads'].get(ident, ())
        evidence = {l: [k for k in reads if any((FORM_HEAD.match(f[1]) or [None, None, None])[2] == l for f in u[k]['forms'])] for l in labels}  # a guess: the own label of a stored form
        by_kind = {l: [k for k in reads if (u[k]['kind'] in ('INIT', 'RIGID_DET')) == suffixed[l]] for l in labels}
        stages = []  # (label -> candidate producers): from the cheapest guess to the widest search, and each decides by the identity alone
        has = sorted(l for l in labels if evidence[l])
        for released in range(min(len(has), 3) + 1):
            for rel in itertools.combinations(has, released):
                stages.append({l: ([k for k in by_kind[l] if k in evidence[l]] or by_kind[l]) if l in has and l not in rel else by_kind[l] for l in labels})
        stages.append({l: list(reads) + [None] for l in labels})
        budget = 100000
        for opts in stages:
            found = []
            for combo in assignments(labels, [opts[l] for l in labels], set(reads)):
                budget -= 1
                forms = [[f[0] for f in u[k]['forms']] if k is not None else [None] for k in combo]
                for pick in itertools.islice(itertools.product(*forms), 2000):
                    if form_ident(text, {l: i for l, i in zip(labels, pick) if i}) == ident:
                        found.append(dict(zip(labels, combo)))
                        break
                if budget <= 0:
                    return None
            if found:
                return found[0] if all(f == found[0] for f in found) else None
        return None

    def union_production(self, task, key):
        """The Production of union table `key`, from the form of its least text length (then least identity), or None where the table has no form."""
        made = self._made.setdefault(task, {})
        if key not in made:
            made[key] = self._union_production(task, key)
        return made[key]

    def _union_production(self, task, key):
        t = self.union[task].get(key)
        if not t or not t['forms']:
            return None
        ident, text = min(t['forms'], key=lambda f: (len(f[1]), f[0]))
        by_label = self.producers(task, key, ident, text)
        if by_label is None:
            return Production(t['query'], len(text), None, 'no assignment of producers gives the form\'s identity', text=text)
        m2g, ins = self.member2g(task), []
        own = FORM_HEAD.match(text)[2]
        for n in FORM_REF.finditer(text[FORM_HEAD.match(text).end():]):
            k = by_label[n[1]]
            if k is None:
                return Production(t['query'], len(text), None, 'a label has no producer in the union', text=text)
            gin = m2g.get(k + n[2])
            if gin is None:  # e.g. an INIT output that the graph makes no table of (gold_union_graph.py: `renamed`): the graph reads the tables of that output's atoms instead
                return Production(t['query'], len(text), None, 'a read (%s) is in no graph table' % (k + n[2]), text=text)
            ins.append((gin, n[2][1:], n[1]))
        return Production(t['query'], len(text), list(dict.fromkeys(ins)), None, text=text, own=own, producers=by_label)


def classify_static(gold, task, reached):
    """{graph table: 0|1|2|None}: 0 reached, 1 inputs not reached, 2 OUT not found, None where the table goes on to the bits."""
    T, k2g = gold.tables[task], gold.key2g(task)
    memo, busy = {}, set()

    def got(k):
        gs = k2g.get(k)
        return True if not gs else any(g in reached for g in gs)

    def complete(g):
        if g in memo:
            return memo[g]
        if g in busy:
            return False
        busy.add(g)
        ok = False
        for alt in gold.alternatives(task, g):
            if all((not k2g.get(k)) or any(g2 in reached and complete(g2) for g2 in k2g[k]) for k in alt):
                ok = True
                break
        busy.discard(g)
        memo[g] = ok
        return ok
    out = {}
    for g, r in T.items():
        if g in reached:
            out[g] = 0
        elif not any(all(got(k) for k in alt) for alt in gold.alternatives(task, g)):
            out[g] = 1
        elif r['goal'] and complete(g):
            out[g] = 2
        else:
            out[g] = None
    return out


# ---------------------------------------------------------------- the job

class Job:
    def __init__(self, folder, gold_names, last=None):
        """The job's sampled queries, with numbers up to `last` where it is given (the --cut of the job's task)."""
        self.draws = []  # (draw number, step hashes of the state, drawn hash)
        self.text_of, outputs, entries = {}, [], []
        self.total, self.solves = 0, False
        for r in draw_file.draws(folder):
            if last is not None and r.get('draw', 0) > last:
                continue
            if 'repeat' in r:
                self.total = max(self.total, r['draw'])
                continue
            if 'steps' not in r:
                continue
            self.total = max(self.total, r['draw'])
            st = r['steps']
            for s in st:
                self.text_of[s['query_hash']] = s['text']
            self.draws.append((r['draw'], tuple(s['query_hash'] for s in st[:-1])))
            self.solves = self.solves or r.get('solves') in (True, 'True')
            q = st[-1]['query_hash']
            for o in r.get('tables') or ():
                outputs.append((q, o['name']))
                for row in o['at']:
                    entries.append((q, o['name'], list(zip(o['dets'], row[:-1])), row[-1]))
        self.names = R.graph_names(outputs, entries)  # (QueryHash, output) -> graph table
        self.gives = collections.defaultdict(list)  # graph table -> [(QueryHash, output)]
        self.of_hash = collections.defaultdict(set)
        for (q, n), g in self.names.items():
            self.gives[g].append((q, n))
            self.of_hash[q].add(g)

    def held_by_draw(self):
        """[(draw number, held graph tables)] for the draws, by the states' queries."""
        out, last, held = [], None, frozenset()
        for d, hs in self.draws:
            if hs != last:
                held = frozenset().union(*[self.of_hash.get(h, ()) for h in hs]) if hs else frozenset()
                last = hs
            out.append((d, held))
        return out


# ---------------------------------------------------------------- the engine

class Engine:
    """The writer's serving walk over a state: needs the run's site, overlay and tree on the path and in the environment, so it imports late."""

    def __init__(self, cfg, order_seconds):
        repo = str(REPO)
        env = os.environ
        code, site = cfg['code'], cfg['site']
        env.update(ARC_MAIN_ROOT=repo, ARC_ROOT=repo, WRITER_ROW_DEADLINE='3600', WRITER_ROW_ORDER_SECONDS=str(order_seconds), WRITER_ROW_TEST_SECONDS='60',
                   WRITER_BODY_NO_ROWS='1', WRITER_VECTOR_OFF='cand', KIT_MODELS=str(Path(code) / 'models-current'), ARCLOG_IDENT_SOURCE='value',
                   RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ARCLOG_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1',
                   ARC_MODELS=cfg['models'], ARC_POLICY=str(Path(code) / 'model/study/policy'), POOL_CLAUSES='search', WRITER='1', WRITER_TREE=cfg['tree'],
                   WRITER_PLAN=cfg['plan'], ORDER_FREE='col,tie,key', P_DAG='1', ONE_REPAIR='30')
        env.update(dict(x.split('=', 1) for x in cfg['env']))
        for p in (repo + '/model/study/samples', site, code + '/model/study/samples', code + '/model/study/sampler'):
            sys.path.insert(0, p)
        import numpy
        import writer  # first: importing live puts the main checkout's model/study first on the path, where an older writer.py stands
        import live
        import live_try
        import order
        import points_write as pw
        import search
        import train_rows
        self.np, self.live, self.live_try, self.order, self.pw, self.search, self.tr, self.writer = numpy, live, live_try, order, pw, search, train_rows, writer
        live_try.P.REPO = env.get('ARC_ROOT', live_try.P.REPO)
        self.sampler = live.Sampler(cfg['models'], steers=())
        self.order_seconds = order_seconds
        self.ids_differ = collections.Counter()

    def open_task(self, task):
        live = self.live
        sess, d, _ = self.live_try.session_of(task)
        run = self.search.SearchRun(self.sampler.pri, sess, time.monotonic() + 86400, d, live.Limits())
        lookahead = (self.search.WRITER_LOOKAHEAD,) if hasattr(self.search, 'WRITER_LOOKAHEAD') else ()  # code with no WRITER_LOOKAHEAD has its rules fixed in the legality mask
        plan = self.writer.default_plan(run, self.search.OR_BITS, *lookahead, self.search.DISTRIBUTION)
        return run, plan

    def stream_of(self, run, scope, text):
        live = self.live
        ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), run.session.settings).decode_stream()
        stream = [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
        kind = run.V.name(stream[0])
        if kind not in live.KIND_TOK:
            raise self.pw.Reject('the kind %s is not written' % kind)
        return kind, stream

    def walk(self, run, plan, st, kind, path, limit, check):
        """(bits, why, worst) of the canonical path `path` (kind token left out) of a query of `kind` at state st."""
        W, np = self.writer, self.np
        worst = None  # (rank, bits, token name, point kind, phase, ids)
        total = 0.0

        kp = st['kind_point']
        kt = self.live.KIND_TOK[kind]
        pt = st['starts'].get(kind)
        if pt is None:
            dec, pg = run.scope(st['scope'])
            pg.new = []
            pt = st['starts'][kind] = W.start_point(run, pg, run.open_form(pg, dec, kind), kind)
        pt0 = pt
        why = ''
        for step, t in enumerate([kt] + list(path)):
            if step == 0:
                ids, fac, reason = kp.ids_, np.zeros(len(kp.ids_)), None
                pt_here, label, phase = kp, 'KIND', 'KIND'
            else:
                pt_here = pt
                ids, fac, reason = W.options(pt_here, plan)
                label, phase = pt_here.kind, pt_here.place.phase.name
                if check and not reason:
                    a, b = set(int(x) for x in ids), set(int(x) for x in W.point_ids(pt_here))
                    self.ids_differ['points'] += 1
                    self.ids_differ['differ'] += a != b
            if reason:
                return math.inf, 'no id left (%s) after %d tokens' % (reason, step), worst
            j = np.nonzero(ids == t)[0]
            if not len(j):
                return math.inf, 'token %s is no id at %s point %d' % (run.V.name(t), phase, step), worst
            j = int(j[0])
            if len(ids) == 1:
                bits, rank = 0.0, 1
            else:
                probs, _ = W.probabilities(pt_here, plan, ids, fac)
                p = float(probs[j])
                if p <= 0:
                    return math.inf, 'chance 0 for %s at %s point %d' % (run.V.name(t), phase, step), worst
                bits, rank = -math.log2(p), 1 + int((probs > probs[j]).sum())
            total += bits
            if worst is None or (rank, bits) > (worst[0], worst[1]):
                worst = (rank, bits, run.V.name(t), label, phase, len(ids))
            if limit is not None and total > limit:
                return total, 'capped', worst
            if step:
                pt = W.step_point(pt_here, int(t), st['cache'])
            else:
                pt = pt0
        return total, why, worst


def scope_of_hashes(hashes, text_of):
    """(the scope's texts over labels &r<position>, {QueryHash: position}) of the steps of a state, or None where a step cannot be written over labels."""
    own, pos = {}, {}
    for i, h in enumerate(hashes):
        m = OWN.match(text_of[h])
        if m is None or m.group(1) in ('RIGID_DET', 'DEMONSTRATED'):
            return None
        own[m.group(2)] = i
        pos[h] = i
    try:
        return [NAME.sub(lambda m: '&r%d' % own[m.group(1)], text_of[h]) for h in hashes], pos
    except KeyError:
        return None


# ---------------------------------------------------------------- one job

@dataclasses.dataclass
class Production:
    """One way to give a graph table: the QueryHash of the query, the length of its text, its inputs as [(graph table, output name, tag)] (None where an input has no
    graph table; `why` then says so), and its text. Where the text is a skeleton record's, `rec` holds it. The tag is what the text calls the input: a producer's QueryHash
    in the skeleton's closure, a label in a union form's text."""
    query: str | None
    size: int
    ins: list | None
    why: str | None = None
    rec: dict | None = None
    text: str | None = None
    own: str | None = None
    producers: dict | None = None  # a union form: {label: union key of the table that it names}

    def write(self, label, own, eng):
        """The text with each input's tag written as its label in the scope (label: {tag: '&r<position>'}) and the query's own label written as `own`."""
        if self.rec is not None:
            return eng.pw.rewrite(self.rec, label, own)

        def put(m):
            if m[1] == self.own:
                return own
            if m[1] in label:
                return label[m[1]] + m[2]
            raise eng.pw.Reject('the label &%s is no input of the production' % m[1])
        return FORM_REF.sub(put, self.text)


def productions(gold, task, g, source):
    """The Productions of graph table g, from the 'union' (its tables' forms, and their reads) or the 'skeleton' (its queries that give g, and the union tables' queries that it has)."""
    if source == 'union':
        got = {}
        for m in gold.tables[task][g]['members']:
            k = m.split('.')[0]
            p = gold.union_production(task, k) if k not in got else None
            if p is not None:
                got[k] = p
        return sorted(got.values(), key=lambda p: p.query or '')  # an order that does not depend on the members' order
    q, by_g = gold.queries(task)
    hs = list(by_g.get(g, ()))
    u = gold.union.get(task, {})
    for m in gold.tables[task][g]['members']:
        h = (u.get(m.split('.')[0]) or {}).get('query')
        if h in q and h not in hs:
            hs.append(h)
    out = []
    for h in hs:
        rec, ins = q[h], []
        for i in rec['inputs']:
            if 'query' not in i:
                continue
            src = q.get(i['query'])
            ins.append((None if src is None else src['graph_tables'].get(i['name']), i['name'], i['query']))
        out.append(Production(h, len(rec['program'][-1]), None if any(x[0] is None for x in ins) else ins, None if all(x[0] is not None for x in ins) else 'an input is not in the skeleton', rec=rec))
    return out


def classify_job(eng, gold, flags, task, job_dir, result, a):
    t0 = time.time()
    T = gold.tables[task]
    last = a.cut_of.get(task)
    job = Job(job_dir, set(T), last)
    D = result.get('draws') or job.total
    D = max(D, job.total) if last is None else min(max(D, job.total), last)
    reached = set(job.gives) & set(T)
    static = classify_static(gold, task, reached)
    rows = {g: dict(t=g, depth=T[g]['depth'], kind=T[g]['kind'], goal=T[g]['goal'], ident=(flags.get(task, {}).get(g) or {}).get('has_ident'), cls=str(c) if c is not None else None) for g, c in static.items()}
    todo = [g for g, c in static.items() if c is None]
    notes = collections.Counter()
    if todo and job.draws:
        held = job.held_by_draw()
        cand = []  # (d, text length, g, production)
        for g in todo:
            prods = productions(gold, task, g, a.productions)
            if not prods:
                rows[g].update(cls='x', why='no gold text in the %s' % a.productions)
                continue
            usable = 0
            for p in prods:
                if p.ins is None:
                    continue
                need = {x[0] for x in p.ins}
                if not need <= reached:
                    continue
                d = next((d for d, h in held if need <= h), None)
                if d is None:
                    continue
                usable += 1
                cand.append((d, p.size, g, p))
            rows[g]['prods'] = len(prods)
            if not usable:
                rows[g].update(cls='x', why='no production with its inputs in one state' if any(p.ins is not None for p in prods) else 'no production has its inputs: %s' % prods[0].why)
        per_g = collections.defaultdict(list)
        for c in sorted(cand, key=lambda c: (c[0], c[1])):
            if len(per_g[c[2]]) < a.max_productions:
                per_g[c[2]].append(c)
        by_d = collections.defaultdict(list)
        for g, cs in per_g.items():
            for c in cs:
                by_d[c[0]].append(c)
        steps_of = dict(job.draws)
        best = {}  # g -> (class, b, detail)
        if by_d:
            run, plan = eng.open_task(task)
        for d in sorted(by_d):
            sc = scope_of_hashes(steps_of[d], job.text_of)
            if sc is None:
                notes['state with a step that cannot be written over labels'] += 1
                for c in by_d[d]:
                    rows[c[2]].setdefault('why', 'state %d: a step cannot be written over labels' % d)
                continue
            texts, pos = sc
            scope = tuple(texts)
            try:
                dec0, pg0 = run.scope(scope)
                pg0.new = []
                kp = eng.writer.kind_point(run, pg0, dec0)
            except Exception as e:  # noqa: BLE001
                notes['state the engine refuses'] += 1
                for c in by_d[d]:
                    rows[c[2]].setdefault('why', 'state %d refused: %s' % (d, str(e).splitlines()[-1][:120] if str(e) else type(e).__name__))
                continue
            st = dict(scope=scope, kind_point=kp, starts={}, cache={})
            after = D - d + 1
            for _, _, g, prod in by_d[d]:
                try:
                    label = {}
                    for gin, name, tag in prod.ins:
                        idx = min((pos[q] for q, n in job.gives[gin] if q in pos and n == name), default=None)
                        if idx is None or label.setdefault(tag, '&r%d' % idx) != '&r%d' % idx:
                            raise eng.pw.Reject('input %s is not one query of the state' % gin)
                    text = prod.write(label, '&r%d' % len(scope), eng)
                    kind, stream = eng.stream_of(run, scope, text)
                    path, order, owhy = eng.order.canonical_stream(eng.tr.order_env(run), dec0, kind, stream[1:], eng.order_seconds)
                    b, why, worst = eng.walk(run, plan, st, kind, path, a.b_limit, a.check_ids)
                except Exception as e:  # noqa: BLE001
                    rows[g].setdefault('why', 'state %d: %s: %s' % (d, type(e).__name__, str(e).splitlines()[-1][:120] if str(e) else ''))
                    notes['production not walked'] += 1
                    continue
                cls = 3 if b > math.log2(D) else 4 if b > math.log2(max(after, 1)) else 5
                cur = best.get(g)
                if cur is None or (cls, -b) > (cur[0], -cur[1]):
                    best[g] = (cls, b, dict(d=d, after=after, order=order, walk=why, tok=worst[2] if worst else None, rank=worst[0] if worst else None, tok_bits=round(worst[1], 2) if worst else None,
                                            n_ids=worst[5] if worst else None, point_kind=worst[3] if worst else None, phase=worst[4] if worst else None, query=prod.query, text=text[:160]))
                rows[g]['evaluated'] = rows[g].get('evaluated', 0) + 1
        for g, (cls, b, det) in best.items():
            rows[g].update(cls=str(cls), b=None if math.isinf(b) else round(b, 2), b_inf=math.isinf(b), **det)
            rows[g].pop('why', None)
        for g in todo:
            if rows[g]['cls'] is None:
                rows[g].update(cls='x', why=rows[g].get('why', 'not scored'))
    for g in todo:
        if rows[g]['cls'] is None:
            rows[g].update(cls='x', why='the job has no sampled query')
    counts = collections.Counter(r['cls'] for r in rows.values())
    return dict(task=task, seed=result['seed'], job=job_dir.name, arm=result['arm'], draws=D, solved=result.get('solved'), cpu=result.get('cpu'), seconds=round(time.time() - t0, 1),
                counts=dict(counts), notes=dict(notes), tables=list(rows.values()))


# ---------------------------------------------------------------- the summary

def read_lines(out):
    base = Path(Z.logical(out))
    names = [str(base)] + sorted({Z.logical(p) for p in base.parent.glob(base.name + '-shard*')})
    for n in names:
        if Z.exists(n):
            for l in Z.open_text(n):
                if l.strip():
                    yield json.loads(l)


def summary(out):
    jobs = list(read_lines(out))
    if not jobs:
        print('no job lines in', out)
        return
    seen, rows = {}, []
    for j in jobs:
        seen[j['job']] = j
    for j in seen.values():
        for r in j['tables']:
            rows.append(dict(r, task=j['task'], D=j['draws']))
    ident = [r for r in rows if r['ident'] is True]
    main = [r for r in rows if r['ident'] is not True]
    print('\n== break points: %d jobs, %d tasks, %d gold tables (%d with an Ident column, counted apart; %d with no flag are counted as no Ident)' % (
        len(seen), len({j['task'] for j in seen.values()}), len(rows), len(ident), sum(r['ident'] is None for r in rows)))

    def line(k, g):
        c = collections.Counter(r['cls'] for r in g)
        print('%-8s %6d %7d %9d | %s' % (k, len(g), c['0'], len(g) - c['0'], ' | '.join('%*d' % (len(CLASS_NAMES[x]), c[x]) for x in CLASS_COLUMNS)))

    def table(title, rs, key, keys):
        print('\n%s' % title)
        print('%-8s %6s %7s %9s | %s' % ('', 'gold', 'reached', 'unreached', ' | '.join(CLASS_NAMES[x] for x in CLASS_COLUMNS)))
        for k in keys:
            line(k, [r for r in rs if key(r) == k])
        line('all', rs)
    kind_of = lambda r: 'OUT' if r['goal'] else r['kind']  # noqa: E731
    kinds = ('DET', 'RULE', 'INIT', 'OUT', 'CHOOSE', 'RIGID_DET')
    print('The class inputs not reached is no class of its own depth: the loss belongs to the earlier depth, where it is counted in its own class.')
    table('By dependency depth, tables with no Ident column', main, lambda r: band(r['depth']), BANDS)
    table('By kind (OUT = the goal table), tables with no Ident column', main, kind_of, kinds)
    table('By dependency depth, tables WITH an Ident column (uncounted, apart)', ident, lambda r: band(r['depth']), BANDS)
    table('By kind (OUT = the goal table), tables WITH an Ident column (uncounted, apart)', ident, kind_of, kinds)
    for title, rs in (('no Ident column', main), ('Ident column (apart)', ident)):
        c3 = [r for r in rs if r['cls'] == '3']
        print('\nWriter rank, %s: %d tables' % (title, len(c3)))
        if not c3:
            continue
        edges = (8, 16, 24, 32, 48, 64)
        hist = collections.Counter()
        for r in c3:
            b = r.get('b')
            hist['inf (not an id / no id)' if r.get('b_inf') else next(('<%d' % e for e in edges if b < e), '>=%d' % edges[-1])] += 1
        print('  b bits: ' + ', '.join('%s: %d' % (k, v) for k, v in sorted(hist.items(), key=lambda kv: (kv[0].startswith('inf'), int(re.sub(r'\D', '', kv[0]) or 0)))))
        print('  lowest-ranked gold token, by phase: ' + ', '.join('%s: %d' % kv for kv in collections.Counter(r.get('phase') for r in c3).most_common()))
        print('  by writing-point kind: ' +', '.join('%s: %d' % kv for kv in collections.Counter(r.get('point_kind') for r in c3).most_common()))
        rk = sorted(r['rank'] for r in c3 if r.get('rank'))
        if rk:
            print('  rank of that token: median %d, 90th %d, max %d' % (rk[len(rk) // 2], rk[int(len(rk) * .9)], rk[-1]))
    print('\nLargest class by depth, no Ident column, inputs not reached left out:')
    for b in BANDS:
        c = collections.Counter(r['cls'] for r in main if band(r['depth']) == b and r['cls'] in '2345')
        print('  depth %-4s %s' % (b, ', '.join('%s %d' % (CLASS_NAMES[k], v) for k, v in sorted(c.items(), key=lambda kv: -kv[1])) or 'none'))
    why = collections.Counter(r.get('why', '')[:60] for r in rows if r['cls'] == 'x')
    if why:
        print('\nNot scored: ' +'; '.join('%s: %d' % kv for kv in why.most_common(8)))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('run')
    ap.add_argument('arm')
    ap.add_argument('out')
    ap.add_argument('--tasks')
    ap.add_argument('--seed', type=int)
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--summary-only', action='store_true')
    ap.add_argument('--union', default=str(R.UNION))
    ap.add_argument('--productions', choices=('union', 'skeleton'), default='union', help='where the productions of a gold table and their inputs come from: the union and its graph (default), or the skeleton')
    ap.add_argument('--skeleton', default=str(SKELETON), help='the skeleton folder, read only with --productions skeleton')
    ap.add_argument('--flags', default=str(DEV161 / 'gold-flags-dev.json'))  # gold_flags.py writes it from the dev row stores
    ap.add_argument('--code')
    ap.add_argument('--site')
    ap.add_argument('--tree')
    ap.add_argument('--models')
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--max-productions', type=int, default=6)
    ap.add_argument('--b-limit', type=float, help='stop a path once its bits pass this; b is then a lower bound (default: the whole path)')
    ap.add_argument('--order-seconds', type=float, default=5.0)
    ap.add_argument('--check-ids', action='store_true', help='count the points where writer.options and writer.point_ids give other ids')
    ap.add_argument('--cut', help='a JSON file of {task: N}: each job of a listed task is read as if it had ended after its sampled query N, so two runs compare at an equal count of '
                                  'sampled queries; its tables, its states and the D of the classes come from those queries alone')
    a = ap.parse_args()
    a.cut_of = json.load(open(a.cut)) if a.cut else {}
    k, n = map(int, a.shard.split('/'))
    out = a.out if n == 1 else '%s-shard%dof%d' % (Z.logical(a.out), k, n)
    if a.summary_only:
        summary(a.out)
        return
    run = Path(a.run) if os.path.isabs(a.run) else DEV161 / a.run
    last = json.loads(open(run / 'runs.jsonl').read().strip().splitlines()[-1])['args']
    cfg = dict(code=a.code or last['code'], site=a.site or last['site'], tree=a.tree or last['tree'], models=a.models or last['models'], plan=last.get('plan', 'ordered'),
               env=DEFAULT_ENV + [x for x in last.get('tok_env', [])] + a.env)
    if not (run / 'results.jsonl').exists():
        print('%s has no results.jsonl yet: no job has finished' % run)
        return
    jobs = {}
    for r in map(json.loads, open(run / 'results.jsonl')):
        if r['arm'] == a.arm and (a.seed is None or r['seed'] == a.seed):
            jobs[r['task'], r['seed']] = r
    gold = Gold(Path(a.union), a.skeleton)
    flags = json.load(open(a.flags)) if os.path.exists(a.flags) else {}
    want = None if not a.tasks else set(open(a.tasks[1:]).read().split()) if a.tasks.startswith('@') else set(a.tasks.split(','))
    done = {j['job'] for j in read_lines(a.out)}
    todo = []
    for (task, seed), r in sorted(jobs.items()):
        folder = run / 'jobs' / r['job']
        if task not in gold.tables or (want and task not in want) or zlib.crc32(task.encode()) % n != k or r['job'] in done or not draw_file.has_draws(folder):
            continue
        todo.append((task, folder, r))
    if a.limit:
        todo = todo[:a.limit]
    print('%s %s: %d finished jobs of the arm, %d done, %d to do%s' % (run.name, a.arm, len(jobs), len(done), len(todo), '' if not flags else ''), flush=True)
    eng = Engine(cfg, a.order_seconds) if todo else None
    t0 = time.time()
    with Z.open_text(out, 'a', line_buffering=True) as f:
        for i, (task, folder, r) in enumerate(todo, 1):
            line = classify_job(eng, gold, flags, task, folder, r, a)
            f.write(json.dumps(line, separators=(',', ':')) + '\n')
            el = time.time() - t0
            print('%s %d/%d %.1f s, counts %s; %.2f jobs/min, ETA %.0f s' % (line['job'], i, len(todo), line['seconds'], json.dumps(line['counts'], sort_keys=True), 60 * i / el, el / i * (len(todo) - i)), flush=True)
    if eng is not None and a.check_ids:
        print('ids check:', dict(eng.ids_differ))
    summary(a.out)


if __name__ == '__main__':
    main()
