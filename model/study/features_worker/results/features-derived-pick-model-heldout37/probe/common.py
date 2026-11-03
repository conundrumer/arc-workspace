"""Shared setup for the probes: ../../features-scope-loss-c-read-heldout37-ramp22/job.py's code up to main, and the N600 contexts.

N600: sampler-pool-dag-nodes-train50-600s, arm nodes_s0, 50 training tasks, none of the 37, the ramp 22 or the 99. Gold text: the train50 kit's
points-eval.json (view-final). A recorded scope is the fids of a visit with resume false, sorted by (bank depth, fid), as job.scope_of sorts them.
"""
import json
import os
import sys
import time

REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker'
N600 = SW + '/sampler-pool-dag-nodes-train50-600s/out/nodes_s0'
N600_GOLD = SW + '/kits/sampler-pool-dag-nodes-train50-final-8be414670/points-eval.json'
HELD = set()
for f in ('tasks.txt', 'ramp-fold.txt', 'leave_out.txt'):
    HELD |= set(open(SW + '/held/' + f).read().split())

_argv = sys.argv
src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
sys.argv = ['job.py']
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
sys.argv = _argv
or_q, live, D, P = ns['or_q'], ns['live'], ns['D'], ns['P']
S = live.S

sys.path.insert(0, HERE)
import feats  # noqa: E402

MEMO = {}
ENV = dict(D=ns['D'], live=live, sampler=ns['sampler'], col_sigs=ns['col_sigs'])


def relations_x(texts, sess, d):
    """feats.replay of the texts, memoized by the texts (clear MEMO when the task changes): the tables with their row counts, and those that do not parse (no_table)."""
    k = tuple(texts)
    if k not in MEMO:
        if len(MEMO) > 400:
            MEMO.clear()
        MEMO[k] = feats.replay(texts, sess, d, ENV)
    return MEMO[k]


def relations(texts, sess, d):
    """REC/job.py:relations: the tables that parse."""
    return {k: v for k, v in relations_x(texts, sess, d).items() if not v['no_table']}


ns['relations'] = relations
_session_of = D.session_of


def session_of(task_id):
    """D.session_of, on the task file the N600 job read (its work/<task>.task.json), else the repo's, where the kit has no copy."""
    p = _task_file(task_id)
    if not os.path.exists(D.S.TASKS + task_id + '.json') and p:
        d = json.load(open(p))
        for t in d['test']:
            t.pop('output', None)
        st = D.arclog.DecodeSettings(relations=D.RELATIONS, **D.SETTINGS)
        return D.arclog.Session(D.arclog.Task.from_json(json.dumps(d), D.arclog.World.Open), st, session_bytes=D.SESSION_BYTES), d, [None] * len(d['test'])
    return _session_of(task_id)


D.session_of = session_of
import live_try as LT  # noqa: E402
_lt_session_of = LT.session_of


def lt_session_of(task):
    """live_try.session_of (the fresh session of each order walk), on the N600 job's task file where the kit has no copy."""
    p = _task_file(task)
    if not os.path.exists('%s/data/tasks/%s.json' % (LT.P.REPO, task)) and p:
        d = json.load(open(p))
        outs = [t.pop('output', None) for t in d['test']]
        sess = live.arclog.Session(live.arclog.Task.from_json(json.dumps(d), live.arclog.World.Open), live.arclog.DecodeSettings(**LT.SETTINGS), session_bytes=2 << 30)
        return sess, d, outs
    return _lt_session_of(task)


LT.session_of = lt_session_of
NGOLD = {x['task']: x['gold_sexp'] for x in json.load(open(N600_GOLD))}


class NCtx:
    """The N600 job of one task: gold lines, bank, recorded scopes."""
    def __init__(self, task):
        assert task not in HELD, task
        self.task = task
        self.lines = [l for l in NGOLD[task].strip().split('\n') if not l.startswith('(OUT')]
        self.heads = [l.split()[1] for l in self.lines]
        w = '%s/%s/work/%s.out.jsonl' % (N600, task, task)
        self.bank = P.load_bank(w + '.bank')
        self.pports = ns['reader_ports'](self.lines, [f.text for f in self.bank['forms'].values()])
        vs = sorted((json.loads(l) for l in open(w + '.visits')), key=lambda v: v['time'])
        fs = self.bank['forms']
        seen, self.scopes = set(), []
        for v in vs:
            if v['resume'] or not v['fids'] or not all(f in fs for f in v['fids']):
                continue
            fids = tuple(sorted(v['fids'], key=lambda f: (fs[f].depth, f)))
            if fids in seen:
                continue
            seen.add(fids)
            self.scopes.append(dict(fids=fids, kind=v['kind'], texts=[fs[f].text for f in fids]))


def gold_read_keys(c, sess, d):
    """[(g, kind, read keys, own keys)] of the gold forms whose refs align with their relation tokens."""
    grel = relations(c.lines, sess, d)
    by_g = {v['slot']: k for k, v in grel.items()}
    out = []
    for g, l in enumerate(c.lines):
        kind = l.split()[0][1:]
        own = {v['key'] for v in grel.values() if v['form'] == g}
        try:
            toks = ns['slots_of'](sess, c.lines[:g], l, kind)
        except Exception:  # noqa: BLE001
            continue
        keys = {grel[by_g[s]]['key'] for s in toks if s in by_g}
        if len(keys) < len({s for s in toks}) and not all(s in by_g for s in toks):
            continue
        if keys:
            out.append((g, kind, keys, own))
    return out


# ---------------------------------------------------------------- C120: the corpus run at 120 s (sampler-cover-clauses-train-120s-c87cf482a)

C120 = SW + '/sampler-cover-clauses-train-120s-c87cf482a/out'
C120_MAC = SW + '/sampler-cover-clauses-train20-120s-c87cf482a/out'  # the 20 tasks of that run that ran on the Mac


def c120_dir(task):
    return C120 if os.path.exists('%s/%s.events.jsonl' % (C120, task)) else C120_MAC
VIEW_FINAL = HERE + '/view-final'  # a snapshot of gold-v3-combined-cut/view-final taken after the gold change of 2026-11-02; manifest.json holds its tree sha256
REPO_TASKS = '/Users/davidlu/code/arc-workspace/data/tasks'


class _F:
    def __init__(self, text, depth, parents):
        self.text, self.depth, self.parents = text, depth, parents


class CCtx:
    """The C120 job of one task: gold lines (view-final, first program), the forms of its node records, recorded scopes from its visit events."""
    def __init__(self, task):
        import gzip
        import re
        import subprocess
        assert task not in HELD, task
        self.task = task
        sexp = json.loads(gzip.open('%s/%s/pairs.jsonl.gz' % (VIEW_FINAL, task), 'rt').readline())['gold_sexp']
        self.lines = [l for l in sexp.strip().split('\n') if not l.startswith('(OUT')]
        self.heads = [l.split()[1] for l in self.lines]
        raw = subprocess.run(['zstd', '-dcq', '%s/%s.nodes.jsonl.zst' % (c120_dir(task), task)], capture_output=True, check=True).stdout.decode()
        forms = {}
        for line in raw.split('\n'):
            if not line:
                continue
            x = json.loads(line)
            t = x['clause']
            fid = int(t.split()[1][2:])
            if fid not in forms:
                forms[fid] = _F(t, x['depth'], sorted({int(m) for m in re.findall(r'&f(\d+)', t)} - {fid}))
        self.bank = dict(forms=forms)
        self.pports = ns['reader_ports'](self.lines, [f.text for f in forms.values()])
        seen, self.scopes = set(), []
        for line in open('%s/%s.events.jsonl' % (c120_dir(task), task)):
            v = json.loads(line)
            if v.get('event') != 'visit' or not v['fids'] or not all(f in forms for f in v['fids']):
                continue
            fids = tuple(sorted(v['fids'], key=lambda f: (forms[f].depth, f)))
            if fids in seen:
                continue
            seen.add(fids)
            self.scopes.append(dict(fids=fids, kind=v['kind'], texts=[forms[f].text for f in fids]))


def _task_file(task_id):
    for p in ('%s/%s/work/%s.task.json' % (N600, task_id, task_id), '%s/%s.json' % (REPO_TASKS, task_id)):
        if os.path.exists(p):
            return p
    return None
