#!/usr/bin/env python3
"""lineage_check.py: fails loudly when a column block is lost between extraction and serving.

A block is a column-name prefix such as `tok_rank:`. Steps, per block:
  1 computed in extraction: the block's columns are in every instance file's header vector_names (all headers are read)
  2 present in the instances: on a sample of point files, the block has non-NaN values and more than one value
  3 named in the served tree: the tree's uses file holds a column of the block; used columns that the instances lack are listed
  4 computed at serving: the parity folder's `token` records hold the block's columns (all of the block's used columns), not all NaN
  5 set the same in both environments (all blocks): every env variable of the extraction script against serving's
Any failed step prints `FAIL <block> step <n> <name>: <evidence>` and the exit status is 1.

Run with a Python that has numpy and zstandard, for example
  work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -I lineage_check.py INSTANCES MODEL EXTRACT_SCRIPT OVERLAY [--blocks tok_rank: tokc: ctx:] [--manifest M.json] [--parity DIR]
"""
import argparse
import ast
import base64
import collections
import glob
import io
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

import numpy as np
import zstandard

# Env variables whose difference is allowed, with the reason. Anything else fails. Extend with --allow NAME=reason.
ALLOWED_EXACT = {
    'ARC_MAIN_ROOT': 'path', 'ARC_ROOT': 'path', 'ARC_MODELS': 'path', 'ARC_POLICY': 'path', 'POLICY_MODEL': 'path', 'ARC_STORE': 'path',
    'KIT_MODELS': 'path', 'PYTHONPATH': 'path', 'WRITER_TREE': 'path of the model file (extraction reads no tree)', 'SEARCH_STATE_SCORE': 'path',
    'NODE_SCORE': 'path', 'ARC_RECORD': 'path of the record output (debug output)', 'WRITER_PARITY_DIR': 'debug output', 'WRITER_ATOM_LOG_DIR': 'debug output',
    'RUST_BACKTRACE': 'debug output', 'ARCLOG_THREADS': 'thread count',
    'ARC_SEED_BASE': 'the search\'s seed (extraction runs no search)', 'POOL_CLAUSES': 'the search that runs (extraction runs no search)',
    'PYTHONDONTWRITEBYTECODE': 'bytecode files, which hold no value',
}
ALLOWED_PATTERNS = [(r'.*_NUM_THREADS', 'thread count'), (r'ARC_DRAW_(RECORD|RUN|SITE|RELEASE)', 'debug output (draw records)'), (r'GATE_RECORD(S|_TASK)', 'debug output (gate records)')]


def allowed_reason(name, extra):
    if name in extra:
        return extra[name]
    if name in ALLOWED_EXACT:
        return ALLOWED_EXACT[name]
    for pat, why in ALLOWED_PATTERNS:
        if re.fullmatch(pat, name):
            return why
    return None


def lines_of(path):
    with open(path, 'rb') as raw:
        r = zstandard.ZstdDecompressor().stream_reader(raw, read_across_frames=True)
        yield from io.TextIOWrapper(r, encoding='utf-8')


def header_of(path):
    for line in lines_of(path):
        return json.loads(line)


def block_of(name):
    return name.split(':', 1)[0] + ':' if ':' in name else name


class Report:
    def __init__(self):
        self.fails = []
        self.out = []

    def say(self, s=''):
        print(s, flush=True)

    def fail(self, block, step, name, evidence):
        msg = 'FAIL %s step %d %s: %s' % (block, step, name, evidence)
        self.fails.append(msg)
        self.say(msg)


# ---------- step 1, 2: instances ----------
def read_headers(folder, rep):
    files = sorted(glob.glob(os.path.join(folder, '*.jsonl.zst')))
    if not files:
        raise SystemExit('lineage_check: no *.jsonl.zst in %s' % folder)
    heads = {}
    for f in files:
        h = header_of(f)
        heads[f] = h
    return files, heads


def sample_values(files, heads, blocks, n_files, n_points, sample_notes):
    """Per block: counts of NaN, total cells, Counter of non-NaN values (rounded), and per column min/max."""
    pick = [files[int(i * len(files) / n_files)] for i in range(n_files)] if len(files) > n_files else list(files)
    stat = {b: dict(cells=0, nan=0, vals=collections.Counter(), cols={}) for b in blocks}
    npts = 0
    for f in pick:
        h = heads[f]
        names = h['vector_names']
        in_point = h['vector_point_cols']
        pset = set(in_point)
        ocols = [n for k, n in enumerate(names) if k not in pset]
        pcols = [names[k] for k in in_point]
        n_vo = len(ocols)
        idx = {b: (np.array([i for i, n in enumerate(ocols) if n.startswith(b)], int), np.array([i for i, n in enumerate(pcols) if n.startswith(b)], int)) for b in blocks}
        seen = 0
        for line in lines_of(f):
            if not line.startswith('{"record":"point"') and '"record": "point"' not in line[:40]:
                continue
            if seen >= n_points:
                break
            rec = json.loads(line)
            seen += 1
            npts += 1
            n = len(rec['ids'])
            vo = np.frombuffer(base64.b64decode(rec['vo']), '<f4').reshape(n, n_vo) if n_vo else None
            vp = np.frombuffer(base64.b64decode(rec['vp']), '<f4')
            for b in blocks:
                oi, pi = idx[b]
                parts = []
                if len(oi):
                    parts.append((vo[:, oi], [ocols[i] for i in oi]))
                if len(pi):
                    parts.append((vp[pi][None, :], [pcols[i] for i in pi]))
                s = stat[b]
                for arr, cn in parts:
                    nanm = np.isnan(arr)
                    s['cells'] += arr.size
                    s['nan'] += int(nanm.sum())
                    good = arr[~nanm]
                    if good.size:
                        u, c = np.unique(good, return_counts=True)
                        for v, k in zip(u.tolist(), c.tolist()):
                            s['vals'][v] += k
                    mn = np.where(nanm, np.inf, arr).min(0)
                    mx = np.where(nanm, -np.inf, arr).max(0)
                    for j, name in enumerate(cn):
                        lo, hi = s['cols'].get(name, (np.inf, -np.inf))
                        s['cols'][name] = (min(lo, float(mn[j])), max(hi, float(mx[j])))
    sample_notes.append('values: %d of %d point files, %d points (up to %d each)' % (len(pick), len(files), npts, n_points))
    return stat


# ---------- step 3: tree ----------
def load_uses(model):
    p = Path(model)
    cand = p.with_suffix('.uses.json')
    if not cand.exists():
        cand = Path(str(p).rsplit('.txt', 1)[0] + '.uses.json')
    if not cand.exists():
        raise SystemExit('lineage_check: no uses file beside %s (looked for %s)' % (model, cand))
    return json.loads(cand.read_text()), cand


def tree_plan(model):
    for p in (Path(str(model) + '.json'), Path(str(model).rsplit('.txt', 1)[0] + '.json')):
        if p.exists():
            try:
                return json.loads(p.read_text()).get('plan')
            except Exception:
                return None
    return None


# ---------- step 4: parity ----------
def parity_stats(folder, blocks):
    stat = {b: dict(cells=0, nan=0, vals=collections.Counter(), cols=set()) for b in blocks}
    allcols = set()
    n = 0
    for path in sorted(glob.glob(os.path.join(folder, 'parity.*.zst'))):
        try:
            for line in lines_of(path):
                rec = json.loads(line)
                if rec.get('record') != 'token':
                    continue
                n += 1
                cols = rec['columns']
                shape = rec['shape']
                X = np.frombuffer(base64.b64decode(rec['X']), '<f4').reshape(shape)
                allcols.update(cols)
                for b in blocks:
                    ci = [i for i, c in enumerate(cols) if c.startswith(b)]
                    if not ci:
                        continue
                    a = X[:, ci]
                    s = stat[b]
                    s['cols'].update(cols[i] for i in ci)
                    nanm = np.isnan(a)
                    s['cells'] += a.size
                    s['nan'] += int(nanm.sum())
                    good = a[~nanm]
                    if good.size:
                        u, c = np.unique(good, return_counts=True)
                        for v, k in zip(u.tolist(), c.tolist()):
                            s['vals'][v] += k
        except Exception as e:  # a truncated file: keep what was read
            print('lineage_check: %s read to its end failed: %r' % (path, e), file=sys.stderr)
    return stat, allcols, n


# ---------- step 5: environments ----------
def expand(text, vars_):
    for _ in range(5):
        new = re.sub(r'\$\{(\w+)\}|\$(\w+)', lambda m: vars_.get(m.group(1) or m.group(2), m.group(0)), text)
        if new == text:
            break
        text = new
    return text


def extraction_env(script):
    """(set: {name: value}, removed: set, argv_tokens) from the script's `env` command; shell variables of simple assignments and `cd` are expanded."""
    text = Path(script).read_text()
    vars_ = {}
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r'cd\s+(\S+)', s)
        if m:
            vars_['PWD'] = m.group(1)
        m = re.fullmatch(r'(\w+)=(\S+)', s)
        if m:
            vars_[m.group(1)] = expand(m.group(2), vars_)
    cmd = None
    for line in text.splitlines():
        if re.search(r'(^|\s)env\s', line) and not line.lstrip().startswith('#'):
            cmd = line
    if cmd is None:
        raise SystemExit('lineage_check: no `env` command in %s' % script)
    toks = shlex.split(expand(cmd.split('env ', 1)[1] if cmd.lstrip().startswith(('exec', 'env')) else cmd, vars_), comments=False)
    sets, removed, i = {}, set(), 0
    while i < len(toks):
        t = toks[i]
        if t == '-u' and i + 1 < len(toks):
            removed.add(toks[i + 1])
            i += 2
        elif re.fullmatch(r'\w+=.*', t):
            k, v = t.split('=', 1)
            sets[k] = v
            i += 1
        else:
            break
    rest = toks[i:]
    return sets, removed, rest


def literal_assigns(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    return out


def dev_run_facts(path):
    tree = ast.parse(Path(path).read_text())
    consts = literal_assigns(tree)
    popped, arms = consts['POPPED'], consts['ARMS']
    fixed = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == 'job_env':
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'dict' and call.args and ast.unparse(call.args[0]) == 'os.environ':
                    for kw in call.keywords:
                        fixed[kw.arg] = kw.value.value if isinstance(kw.value, ast.Constant) else '<%s>' % ast.unparse(kw.value)
    return popped, arms, fixed


def worker_defaults(overlay):
    path = Path(overlay) / 'model/study/sampler/kaggle_worker.py'
    tree = ast.parse(path.read_text())
    consts = literal_assigns(tree)
    out = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == 'settings':
            for loop in ast.walk(fn):
                if isinstance(loop, ast.For) and isinstance(loop.iter, ast.Tuple):
                    for pair in loop.iter.elts:
                        if isinstance(pair, ast.Tuple) and len(pair.elts) == 2 and isinstance(pair.elts[0], ast.Constant):
                            v = pair.elts[1]
                            val = consts.get(v.id) if isinstance(v, ast.Name) else (v.value if isinstance(v, ast.Constant) else None)
                            if val is not None:
                                out[pair.elts[0].value] = val
    return out


def argv_values(argv, flag):
    return [argv[i + 1] for i, t in enumerate(argv) if t == flag and i + 1 < len(argv)]


def serving_envs(dev_run, overlay, manifest, command, model):
    """{arm: {name: (value, source)}} for each non-base arm of the manifest's dev_run command."""
    popped, arms, fixed = dev_run_facts(dev_run)
    defaults = worker_defaults(overlay)
    plan = tree_plan(model)
    base = {}
    argv = []
    if manifest:
        m = json.loads(Path(manifest).read_text())
        cmds = [c for c in m['commands'] if (command is None and any('dev_run.py' in a for a in c['argv'])) or c['name'] == command]
        if not cmds:
            raise SystemExit('lineage_check: no dev_run command in %s' % manifest)
        c = cmds[0]
        argv = c['argv']
        base = {k: (v, 'manifest env') for k, v in c['env'].items()}
    arm_list = (argv_values(argv, '--arms') or ['tree'])[0].split(',')  # dev_run's default --arms
    out = {}
    for arm in [a for a in arm_list if a != 'base']:
        env = dict(base)
        for k in popped:
            env.pop(k, None)
        for k, v in fixed.items():
            env[k] = (v, 'dev_run job_env')
        tree_arg = (argv_values(argv, '--tree') or [str(model)])[0]
        for k, v in arms[arm].items():
            env[k] = (v if v is not None else tree_arg, 'dev_run ARMS[%s]' % arm)
        if plan:
            env['WRITER_PLAN'] = (plan, 'dev_run: the plan that the tree records')
        for kv in argv_values(argv, '--tok-env'):
            k, v = kv.split('=', 1)
            env[k] = (v, 'dev_run --tok-env')
        if argv_values(argv, '--node-score'):
            env['NODE_SCORE'] = (argv_values(argv, '--node-score')[0], 'dev_run --node-score')
        if argv_values(argv, '--lookahead') and 'WRITER_TREE' in arms[arm]:
            env['WRITER_LOOKAHEAD'] = (argv_values(argv, '--lookahead')[0], 'dev_run --lookahead')
        if '--record' in argv:
            for k in ('ARC_DRAW_RECORD', 'ARC_DRAW_RUN', 'ARC_DRAW_SITE', 'ARC_DRAW_RELEASE'):
                env[k] = ('<set>', 'dev_run --record')
        for k, v in defaults.items():
            if k not in env:
                env[k] = (v, 'kaggle_worker.settings() default')
        out[arm] = env
    return out, argv


def check_env(rep, extract, manifest, command, overlay, model, dev_run, extra_allow):
    sets, removed, rest = extraction_env(extract)
    ext = {k: (v, 'extraction script') for k, v in sets.items()}
    plan_args = argv_values(rest, '--plan')
    if plan_args:
        ext['WRITER_PLAN'] = (plan_args[0], 'extraction --plan')
    serv_by_arm, argv = serving_envs(dev_run, overlay, manifest, command, model)
    rep.say('step 5 environments: extraction sets %d variables, removes %s' % (len(sets), sorted(removed) or 'none'))
    rep.say('  serving = %s%s, arms %s' % (('manifest ' + Path(manifest).name + ' + ') if manifest else '', 'dev_run job_env + kaggle_worker.settings()', list(serv_by_arm)))
    rows = []
    for arm, serv in serv_by_arm.items():
        for name in sorted(set(ext) | set(serv) | removed):
            e = ext.get(name, (None, ''))[0]
            if name in removed:
                e = None
            s = serv.get(name, (None, ''))[0]
            if e == s:
                continue
            why = allowed_reason(name, extra_allow)
            rows.append((arm, name, e, s, serv.get(name, (None, '-'))[1], why))
    for arm, name, e, s, src, why in rows:
        shown = lambda v: 'unset' if v is None else repr(v)
        tag = 'allowed (%s)' % why if why else 'NOT ALLOWED'
        rep.say('  [%s] %s: extraction %s | serving %s [%s] -> %s' % (arm, name, shown(e), shown(s), src, tag))
        if not why:
            rep.fail('*', 5, 'environment', '%s differs: extraction %s, serving %s (arm %s, from %s)' % (name, shown(e), shown(s), arm, src))
    if not rows:
        rep.say('  no differences')
    rep.say('  note: variables that neither side sets in text (the caller shell\'s own) are not seen')


def pct(a, b):
    return '%.1f%%' % (100.0 * a / b) if b else 'n/a'


def top_value(vals):
    if not vals:
        return 'none'
    v, k = vals.most_common(1)[0]
    return '%g (%d cells)' % (v, k)


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('instances')
    ap.add_argument('model')
    ap.add_argument('extract')
    ap.add_argument('overlay')
    ap.add_argument('--blocks', nargs='*', help='prefixes such as tok_rank: ; default every prefix in the uses file')
    ap.add_argument('--manifest')
    ap.add_argument('--command', help='name of the manifest command; default the first that runs dev_run.py')
    ap.add_argument('--parity')
    ap.add_argument('--dev-run', default='/Users/davidlu/code/arc-workspace/model/study/search/dev161/dev_run.py')
    ap.add_argument('--sample-files', type=int, default=12)
    ap.add_argument('--sample-points', type=int, default=300)
    ap.add_argument('--allow', action='append', default=[], metavar='NAME=reason')
    ap.add_argument('--json', help='write the results to this file')
    a = ap.parse_args()
    extra = dict(x.split('=', 1) for x in a.allow)
    rep = Report()
    uses, uses_path = load_uses(a.model)
    blocks = a.blocks or sorted({block_of(u) for u in uses})
    blocks = [b if b.endswith(':') else b + ':' for b in blocks]
    rep.say('lineage_check: %d blocks, uses file %s (%d names)' % (len(blocks), uses_path.name, len(uses)))

    files, heads = read_headers(a.instances, rep)
    nsets = collections.Counter(tuple(h['vector_names']) for h in heads.values())
    have_all = set.intersection(*[set(h['vector_names']) for h in heads.values()])
    have_any = set.union(*[set(h['vector_names']) for h in heads.values()])
    rep.say('instances: %d files, %d distinct headers, %d columns in every file, %d in some' % (len(files), len(nsets), len(have_all), len(have_any)))
    notes = []
    stat = sample_values(files, heads, blocks, a.sample_files, a.sample_points, notes)
    rep.say('  ' + notes[0])
    if a.parity:
        pstat, pcols, pn = parity_stats(a.parity, blocks)
        rep.say('parity: %s, %d token records, %d columns' % (a.parity, pn, len(pcols)))
    else:
        pstat, pcols, pn = None, None, 0

    result = {}
    used_missing = sorted(u for u in uses if u not in have_all)
    for b in blocks:
        rep.say('')
        rep.say('block %s' % b)
        r = result[b] = {}
        bused = [u for u in uses if u.startswith(b)]
        # step 1
        per_file_missing = [Path(f).name for f, h in heads.items() if not any(n.startswith(b) for n in h['vector_names'])]
        ncols = sum(1 for n in have_any if n.startswith(b))
        r['step1'] = dict(columns_in_some=ncols, files_without=len(per_file_missing))
        if per_file_missing or not ncols:
            rep.fail(b, 1, 'computed in extraction', '%d of %d instance files have no %s column in vector_names (e.g. %s); %d columns in some file' % (len(per_file_missing), len(files), b, per_file_missing[:3], ncols))
        else:
            rep.say('  step 1 ok: %d columns in vector_names of all %d files' % (ncols, len(files)))
        # step 2
        s = stat[b]
        cols = s['cols']
        live = [c for c, (lo, hi) in cols.items() if lo < hi]
        dead = [c for c, (lo, hi) in cols.items() if lo >= hi]
        r['step2'] = dict(cells=s['cells'], nan_share=(s['nan'] / s['cells'] if s['cells'] else None), top_value=top_value(s['vals']), live_columns=len(live), dead_columns=len(dead))
        rep.say('  step 2: %d cells, NaN %s, most common value %s, %d columns vary, %d constant or all-NaN' % (s['cells'], pct(s['nan'], s['cells']), top_value(s['vals']), len(live), len(dead)))
        if not s['cells']:
            rep.fail(b, 2, 'present in instances', 'no cells of %s in the sampled points' % b)
        elif s['nan'] == s['cells']:
            rep.fail(b, 2, 'present in instances', 'all %d sampled cells are NaN' % s['cells'])
        elif len(s['vals']) < 2:
            rep.fail(b, 2, 'present in instances', 'all %d non-NaN sampled cells hold one value %s (NaN %s)' % (s['cells'] - s['nan'], top_value(s['vals']), pct(s['nan'], s['cells'])))
        # step 3
        miss = [u for u in bused if u not in have_all]
        r['step3'] = dict(used_columns=len(bused), used_lacking_in_instances=len(miss))
        if not bused:
            rep.fail(b, 3, 'named in served tree', 'the uses file %s names no %s column' % (uses_path.name, b))
        else:
            rep.say('  step 3: tree uses %d columns of the block' % len(bused))
        if miss:
            rep.fail(b, 3, 'named in served tree', '%d used columns are not in the instances: %s%s' % (len(miss), miss[:6], ' ...' if len(miss) > 6 else ''))
        # step 4
        if pstat is None:
            rep.say('  step 4: not checked (no parity folder)')
            r['step4'] = 'not checked'
        else:
            p = pstat[b]
            smiss = [u for u in bused if u not in pcols]
            r['step4'] = dict(serving_columns=len(p['cols']), cells=p['cells'], nan_share=(p['nan'] / p['cells'] if p['cells'] else None), top_value=top_value(p['vals']), used_not_in_serving=len(smiss))
            rep.say('  step 4: serving rows hold %d columns of the block, %d cells, NaN %s, most common value %s' % (len(p['cols']), p['cells'], pct(p['nan'], p['cells']), top_value(p['vals'])))
            if not p['cols']:
                rep.fail(b, 4, 'computed at serving', 'no %s column in the %d serving token records (%d columns in all); the tree uses %d of them, e.g. %s' % (b, pn, len(pcols), len(bused), bused[:3]))
            elif p['nan'] == p['cells']:
                rep.fail(b, 4, 'computed at serving', 'all %d serving cells of %s are NaN' % (p['cells'], b))
            elif smiss:
                rep.fail(b, 4, 'computed at serving', '%d of %d used columns are not in the serving rows: %s%s' % (len(smiss), len(bused), smiss[:6], ' ...' if len(smiss) > 6 else ''))
    rep.say('')
    if used_missing:
        rep.say('used columns that the instances lack (all blocks): %d' % len(used_missing))
        for u in used_missing[:40]:
            rep.say('  ' + u)
    check_env(rep, a.extract, a.manifest, a.command, a.overlay, a.model, a.dev_run, extra)
    elapsed = time.time() - t0
    rep.say('')
    rep.say('%d failures in %.1f s' % (len(rep.fails), elapsed))
    for f in rep.fails:
        rep.say(f)
    if a.json:
        Path(a.json).write_text(json.dumps(dict(blocks=result, failures=rep.fails, used_missing=used_missing, seconds=elapsed), indent=1, default=str))
    sys.exit(1 if rep.fails else 0)


if __name__ == '__main__':
    main()
