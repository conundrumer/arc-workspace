"""Read of the refit node score arm against the bundle, and the shared helpers of the refit check and smoke scripts.

  <python> -I search_refit_read.py RUN_FOLDER OUT.json [--returns DIR] [--ident FILE] [--gold FILE]

RUN_FOLDER   the folder that holds out/<arm>/<task>/ as run3600.sh writes it (or the out folder itself), and beside it, in the folder or up to two folders above it,
             the files that search_refit_build.py writes: the jobs files, refit-tasks.json, gold-ident-only-refit.json and points-eval.json.
OUT.json     the verdict. It is written each time the script runs, with `final` true only where every job of the main jobs file ended and is valid.
--returns    a folder where the script also writes verdict.json, covered-tables.jsonl and run.txt (the run folder path), each through a temp file and a rename.
Environment: READ_CACHE (default RUN_FOLDER/read-cache.json), READ_SEED, and as in search_node_score_read.py. READ_IDENT, READ_GOLD and READ_TASKS name the files
that the script otherwise looks for beside the run.

Arms: `bundle` and `refit` on the 37 held-out tasks and the 22 ramp tasks, seeds 0 and 1000 (names _s0 and _s1). The check arms parity and refitcheck, and the positives arm
refitp, are read as plain arms. A job's marker name is the file stem of the NODE_SCORE it ran with, as the jobs files give it.

Verdict rule, on the 37 alone: the refit arm passes where, on both seeds, its forms covered are not below the bundle's by more than the noise band, and its Ident-only forms
are above the bundle's. Noise band: the absolute difference between the bundle's seed 0 and seed 1 forms covered, summed over the 37 tasks that have all 4 jobs valid.
The ramp figures are training figures and no rule reads them.

What is printed: the tables of search_node_score_read.py (forms covered, cost, chance per opening, jobs not valid), the figures of the verdict, and the files written.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import time

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH_WORKER = os.environ.get("REFIT_SEARCH_WORKER", "/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker")
sys.path[:0] = [HERE, SEARCH_WORKER]
import search_node_score_read as R  # noqa: E402
import search_node_score_parity as PA  # noqa: E402

PROMOTION_SEEDS = (0, 1)
SEED_NAME = {0: '0', 1: '1000'}
TASK_FILES = dict(tasks='refit-tasks.json', ident='gold-ident-only-refit.json', gold='points-eval.json', gold_n600='points-n600.json')
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+) (?P<models>\S+) (?P<seconds>\d+)\s*$')
FALLBACKS = PA.FALLBACKS
ERROR_SHARE = R.ERROR_SHARE
RAMP_NOTE = ('The 22 ramp tasks are training tasks of models-tk, not of the node score: the node score was fit with the 37, the 22, the 99 and the drifted tasks left out. '
             'The figures are training figures of models-tk. The promotion rule does not read them.')


# ---- the format of the covered tables: the only place that names the fields of a row ----

def covered_row(task, seed, arm, gold, cover, node, form):
    """The row of one covered gold form: the task, the seed, the gold index, the node that covered it, the node's form text and its table key.
    cover is the cover line, node and form are the bank's records of the node (None where the bank does not hold the node)."""
    return dict(task=task, seed=seed, arm=arm, gold=gold, node=cover['node'], draw=cover.get('draw'), depth=cover.get('depth'),
                form_text=getattr(form, 'text', None) if form is not None else None, clause=getattr(node, 'clause', None) if node is not None else None,
                table_key=table_key(node), table_types=getattr(node, 'table_types', None) if node is not None else None, in_bank=node is not None)


def table_key(node):
    """The table key of a bank node: the node's sorted table column types, then the digest of its examples, which hold the order-free row hashes of the table under the Ident source of the run."""
    if node is None:
        return None
    types = ','.join(sorted(str(t) for t in node.table_types))
    return '%s:%s' % (types, hashlib.sha256(json.dumps(node.examples).encode()).hexdigest()[:16])


def task_line(task, seed, arm, work, rows):
    """The line of one task in the covered tables file: the paths of the job's files and its covered rows."""
    return dict(task=task, seed=seed, arm=arm, picks=work + '.out.jsonl.picks', bank=work + '.out.jsonl.bank', cover=work + '.out.jsonl.cover',
                records=os.path.dirname(os.path.dirname(work)), covered=rows)


# ---- files beside the run ----

MAIN_ARMS = ('bundle', 'refit', 'parity', 'refitcheck')


def search_dirs(run):
    """The folders where the files of a run are looked for: the run folder, the two above it, and the kits folder beside the runs folder."""
    run = os.path.abspath(run)
    top = os.path.dirname(os.path.dirname(run))
    return [run, os.path.dirname(run), top, os.path.join(top, 'kits')]


def round_of(run):
    m = re.search(r'refit-(r\d+)-', os.path.basename(os.path.abspath(run)))
    return m[1] if m else None


def kit_tar(run):
    """The kit tar of the run's round (search-refit-rN-kit-*.tar.gz) in the search folders, or the newest refit kit tar where the run name has no round."""
    import glob
    rnd = round_of(run)
    found = []
    for d in search_dirs(run):
        found += glob.glob(os.path.join(d, 'search-refit-%s-kit-*.tar.gz' % (rnd or 'r*')))
    return max(found, key=os.path.getmtime) if found else None


def from_kit(run, member):
    """The path of a file of the kit's root, taken out of the kit tar into a temp folder named by the tar's size and time, or None."""
    import tarfile
    tar = kit_tar(run)
    if not tar:
        return None
    dest = os.path.join(tempfile.gettempdir(), 'refit-aux-%s' % hashlib.sha256(('%s %d %d' % (tar, os.path.getsize(tar), os.path.getmtime(tar))).encode()).hexdigest()[:12])
    path = os.path.join(dest, member)
    if not os.path.exists(path):
        with tarfile.open(tar) as t:
            names = {m.name: m for m in t.getmembers()}
            top = next(n for n in names if '/' not in n)
            key = '%s/%s' % (top, member)
            if key not in names:
                return None
            os.makedirs(dest, exist_ok=True)
            with t.extractfile(names[key]) as f:
                write_atomic(path, f.read().decode()) if member.endswith(('.txt', '.json')) else None
    return path


def find_file(run, name, env=None):
    """A file of the run: the environment variable, else the search folders, else the kit tar."""
    if env and os.environ.get(env):
        return os.environ[env]
    for d in search_dirs(run):
        if os.path.exists(os.path.join(d, name)):
            return os.path.join(d, name)
    return from_kit(run, name)


def find_jobs(run):
    """The jobs files of the run's round: search-refit-rN-*jobs*.txt, smoke-jobs.txt and positives-jobs.txt in the search folders, else those at the root of the kit tar."""
    import glob
    rnd = round_of(run)
    patterns = ['search-refit-%s-*jobs*.txt' % (rnd or 'r*'), 'smoke-jobs.txt', 'positives-jobs.txt']
    found = []
    for d in search_dirs(run):
        for g in patterns:
            found += sorted(glob.glob(os.path.join(d, g)))
    if not any('heldout37' in os.path.basename(p) for p in found):
        tar = kit_tar(run)
        if tar:
            import tarfile
            with tarfile.open(tar) as t:
                roots = [n for n in t.getnames() if n.count('/') == 1 and n.endswith('.txt') and 'jobs' in n]
            found += [p for p in (from_kit(run, n.split('/', 1)[1]) for n in roots) if p]
    return found


def parse_jobs(paths):
    """{arm: [spec]} of the job lines, with the arm name without its seed part. A spec holds the task, the seed number (0 or 1), the NODE_SCORE file stem,
    whether NODE_SCORE_CHECK is on, the NODE_SCORE_MIX text, the seconds and the name of the jobs file."""
    arms = collections.defaultdict(list)
    seen = set()
    for p in paths:
        for line in open(p):
            m = LINE.match(line.strip())
            if not m:
                continue
            head = m['head']
            score = re.search(r'NODE_SCORE=\$PWD/scores/(\w+)\.npz', head)
            mix = re.search(r'NODE_SCORE_MIX=(\S+)', head)
            base, seed = m['arm'].rsplit('_s', 1)
            if (m['arm'], m['task']) in seen:
                continue
            seen.add((m['arm'], m['task']))
            arms[base].append(dict(task=m['task'], arm=base, seed=int(seed), score=score[1] if score else None, check='NODE_SCORE_CHECK=1' in head,
                                   mix=mix[1] if mix else None, seconds=int(m['seconds'])))
    return arms


def expected_names(arms):
    """{arm: node score name or None}: the marker name that a job of the arm must show. Each arm must name one score only."""
    want = {}
    for arm, specs in arms.items():
        names = {s['score'] for s in specs}
        if len(names) != 1:
            raise SystemExit('arm %s has lines with node scores %s' % (arm, sorted(names, key=str)))
        want[arm] = names.pop()
    return want


def arm_of(name):
    """The arm name of a job name without its seed part: bundle_s0 gives bundle."""
    return re.sub(r'_s\d+$', '', name)


# ---- one job, light ----

def read_text(path):
    return open(path, errors='replace').read() if os.path.exists(path) else ''


def job_paths(folder, task):
    work = '%s/work/%s' % (folder, task)
    return dict(log=work + '.log', bank=work + '.out.jsonl.bank', picks=work + '.out.jsonl.picks', cover=work + '.out.jsonl.cover', work=work)


def start_time(folder):
    try:
        return float(open(folder + '/start').read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def cover_times(folder, task):
    """{gold index: seconds from the job's start file to its first cover line} (None where the job has no start file)."""
    t0 = start_time(folder)
    got = {}
    for x in PA.read_lines(job_paths(folder, task)['cover']):
        if t0 is not None and 'gold' in x and 'time' in x:
            got[x['gold']] = min(got.get(x['gold'], 1e18), x['time'] - t0)
    return got if t0 is not None else None


def job_ended(folder, seconds):
    """True where the supervisor log of the job has its status line `status at <seconds> s`, or the line `task <id> lives <n> candidates <c> done 1 of 1 at <s>` that it writes when the task ends, as where the last process renews too close to the end to start again. The `end:` line of the worker log is not used: a worker that renews prints one at each renewal."""
    log = read_text(folder + '/supervisor.log')
    return re.search(r'status at %d s' % seconds, log) is not None or re.search(r'^\S+ task \S+ lives \d+ candidates \d+ done 1 of 1 at ', log, re.M) is not None


def past_seconds(folder, task, secs, seconds):
    """True where the files of the job show it ran past secs seconds: it ended (its line gave seconds), or a file of it was written more than secs seconds after the start file."""
    t0 = start_time(folder)
    if t0 is None:
        return False
    p = job_paths(folder, task)
    if job_ended(folder, seconds):
        return True
    stamps = [os.path.getmtime(f) for f in (p['log'], p['cover'], p['picks'], folder + '/supervisor.log') if os.path.exists(f)]
    stamps += [x['time'] for x in PA.read_lines(p['cover'])[-1:] if 'time' in x]
    return bool(stamps) and max(stamps) - t0 > secs


def quick_job(folder, task, want, mix, seconds, with_bank=True):
    """A light read of one job: whether it ended (job_ended, with the seconds of its line), its node score marker lines, fallbacks, deaths and kills, ns_errors and the bank's nodes.
    want is the marker name the job must show (None: no marker), mix the NODE_SCORE_MIX text of its line or None."""
    p = job_paths(folder, task)
    log = read_text(p['log'])
    rec = dict(exists=os.path.isdir(folder), ended=job_ended(folder, seconds), why=[], deaths=None, kills=None, nodes=None, ns_errors=None)
    markers = sorted(set(re.findall(r'^node score: .*$', log, re.M)))
    found = [f for f in FALLBACKS if f in log]
    if found:
        rec['why'].append('log has ' + ', '.join(found))
    if want is None:
        if markers:
            rec['why'].append('node score line in a job with no node score: ' + markers[0])
    else:
        fields = [dict(kv.split('=', 1) for kv in m[len('node score: '):].split()) for m in markers]
        names = {f.get('name') for f in fields}
        if len(markers) > 1:
            rec['why'].append('%d distinct node score lines' % len(markers))
        if markers and names != {want}:
            rec['why'].append('node score line names %s, want %s' % (sorted(names, key=str), want))
        if len(markers) == 1:
            f = fields[0]
            if mix is not None and float(f.get('mix', 'nan')) != float(mix):
                rec['why'].append('marker mix %s, want %s' % (f.get('mix'), mix))
            if mix is None and 'mix' in f:
                rec['why'].append('marker has mix=%s, the line has none' % f['mix'])
    sup = read_text(folder + '/supervisor.log')
    m = re.findall(r'deaths (\d+) kills (\d+)', sup)
    if m:
        rec['deaths'], rec['kills'] = int(m[-1][0]), int(m[-1][1])
    if with_bank and rec['ended'] and os.path.exists(p['bank']):
        bank = PA.load_bank(p['bank'])
        rec['nodes'] = len(bank['nodes'])
        rec['ns_errors'] = bank['policy'].get('ns_errors', 0)
        rec['bank'] = bank
    return rec


# ---- the read ----

def write_atomic(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(os.path.abspath(path)), delete=False, prefix='.tmp-') as f:
        f.write(text)
    os.replace(f.name, path)


class Context:
    """What the patched functions of search_node_score_read.py need: the tasks, the arms' specs, the loaded banks and the progress."""
    run = None
    cfg = None
    specs = {}
    want = {}
    last_bank = {}
    todo = 0
    done = 0
    t0 = 0.0


def job_record(arm, task, folder, info, ident):
    """search_node_score_read.job_record, with the mix check, the cover times and, for the covered tables, the covered rows of the arms refit and refitp."""
    C = Context
    base, _, seed = R.parse_arm(arm)
    seconds = next((x['seconds'] for x in C.specs.get(base, []) if x['task'] == task and x['seed'] == seed), None)
    if seconds is not None and not job_ended(folder, seconds):
        return dict(ended=False, valid=False, why=['open'], covered=sorted({x['gold'] for x in PA.read_lines(job_paths(folder, task)['cover']) if 'gold' in x}), det=0, ident=0,
                    left_out=None, runs=None, ready=0, ns_ms=[], take=None, nodes=None, deaths=None, kills=None, cover_t={}, rows=[], seed_name=SEED_NAME.get(seed, str(seed)))
    rec = ORIG_RECORD(arm, task, folder, info, ident)
    p = job_paths(folder, task)
    specs = C.specs.get(base, [])
    mix = specs[0]['mix'] if specs else None
    if rec['ended'] and C.want.get(base) is not None:
        for mk in set(re.findall(r'^node score: .*$', read_text(p['log']), re.M)):
            f = dict(kv.split('=', 1) for kv in mk[len('node score: '):].split())
            if (mix is None) != ('mix' not in f) or (mix is not None and float(f['mix']) != float(mix)):
                rec['why'].append('marker mix %s, want %s' % (f.get('mix'), mix))
                rec['valid'] = False
    rec['cover_t'] = {str(g): round(t, 2) for g, t in (cover_times(folder, task) or {}).items()}
    rec['seed_name'] = SEED_NAME.get(seed, str(seed))
    rec['rows'] = []
    wanted = (base == 'refit' and task in C.cfg.get('ramp22', ())) or base == 'refitp'
    if rec['ended'] and wanted:
        rec['rows'] = rows_of_job(base, task, seed, p, C.last_bank.get(p['bank']))
    C.done += 1
    el = time.time() - C.t0
    rate = C.done / el if el > 0 else 0.0
    print('read %d/%d %s/%s, %.2f jobs/s, eta %.0f s' % (C.done, C.todo, arm, task, rate, (C.todo - C.done) / rate if rate else 0), file=sys.stderr, flush=True)
    return rec


def rows_of_job(base, task, seed, p, bank):
    """The covered rows of a job, one per gold form its cover lines give: the earliest cover line whose node the bank holds, else the earliest line."""
    covers = PA.read_lines(p['cover'])
    if not covers:
        return []
    nodes = bank['nodes'] if bank else {}
    forms = bank['forms'] if bank else {}
    kept = [(e['proc'], e['nodes0'], e['nodes1']) for e in bank['lineage']] if bank else []
    by_gold = collections.defaultdict(list)
    for x in covers:
        if 'gold' in x and 'node' in x:
            by_gold[x['gold']].append(x)
    rows = []
    for g in sorted(by_gold):
        lines = sorted(by_gold[g], key=lambda x: x.get('time', 0))
        held = [x for x in lines if any(x.get('proc') == pr and a <= x['node'] < b for pr, a, b in kept)]
        x = (held or lines)[0]
        node = nodes.get(x['node']) if held else None
        rows.append(covered_row(task, SEED_NAME.get(seed, str(seed)), base, g, x, node, forms.get(node.form) if node is not None else None))
    return rows


def band_figures(groups, tasks, rng):
    """The figures of the arm `refit` against `bundle` on a task list, over the tasks whose 4 jobs are valid."""
    def rec(arm, s, t):
        return groups.get((arm, False), {}).get(s, {}).get(t)
    ok = sorted(t for t in tasks if all((rec(a, s, t) or {}).get('valid') for a in ('bundle', 'refit') for s in PROMOTION_SEEDS))
    measures = dict(forms_covered=lambda r: len(r['covered']), ident_only=lambda r: r['ident'], det=lambda r: r['det'])
    fig = dict(tasks_listed=len(tasks), tasks_counted=len(ok), per_seed={}, mean_of_seeds={})
    for s in PROMOTION_SEEDS:
        fig['per_seed'][SEED_NAME[s]] = {name: dict(bundle=int(sum(f(rec('bundle', s, t)) for t in ok)), refit=int(sum(f(rec('refit', s, t)) for t in ok)))
                                         for name, f in measures.items()}
        for v in fig['per_seed'][SEED_NAME[s]].values():
            v['D'] = v['refit'] - v['bundle']
    for name, f in measures.items():
        diff = [np.mean([f(rec('refit', s, t)) for s in PROMOTION_SEEDS]) - np.mean([f(rec('bundle', s, t)) for s in PROMOTION_SEEDS]) for t in ok]
        pt, lo, hi = R.band(diff, np.random.default_rng(int(os.environ.get('READ_SEED', 1)))) if ok else (None, None, None)
        fig['mean_of_seeds'][name] = dict(D=pt, band90=[lo, hi])
    b0, b1 = (fig['per_seed'][SEED_NAME[s]]['forms_covered']['bundle'] for s in PROMOTION_SEEDS)
    fig['noise_band'] = abs(b0 - b1)
    return fig


def newly_covered(groups, tasks):
    """The rows of the gold forms that a refit job covered and no bundle job of the task covered, one per task and gold form, with the seeds of the refit jobs."""
    out = []
    for t in tasks:
        bundle = set()
        for s in PROMOTION_SEEDS:
            r = groups.get(('bundle', False), {}).get(s, {}).get(t)
            bundle |= set(r['covered']) if r and r['ended'] else set()
        seen = {}
        for s in PROMOTION_SEEDS:
            r = groups.get(('refit', False), {}).get(s, {}).get(t)
            for row in (r or {}).get('rows', ()):
                if row['gold'] not in bundle:
                    got = seen.setdefault(row['gold'], dict(row, seeds=[]))
                    got['seeds'].append(SEED_NAME[s])
                    got.pop('seed', None)
        out += [seen[g] for g in sorted(seen)]
    return out


def verdict(groups, c1, rng):
    C = Context
    cfg = C.cfg
    t37, ramp = cfg['heldout37'], cfg['ramp22']
    f37 = band_figures(groups, t37, rng)
    N = f37['noise_band']
    seeds = {}
    for s in PROMOTION_SEEDS:
        v = f37['per_seed'][SEED_NAME[s]]
        seeds[SEED_NAME[s]] = dict(forms_ok=v['forms_covered']['D'] >= -N, ident_up=v['ident_only']['D'] > 0)
    have = f37['tasks_counted'] > 0 and all(groups.get(('refit', False), {}).get(s) for s in PROMOTION_SEEDS)
    passed = bool(have and all(v['forms_ok'] and v['ident_up'] for v in seeds.values()))
    wanted = main_jobs(C.specs)
    recs = {}
    for (base, fold), by_seed in groups.items():
        for seed, by_task in by_seed.items():
            for task, rec in by_task.items():
                recs['%s_s%d/%s' % (base + ('f' if fold else ''), seed, task)] = rec
    jobs = dict(expected=len(wanted), ended=0, valid=0, open=[], invalid=[])
    for name in wanted:
        r = recs.get(name)
        if r is None or not r['ended']:
            jobs['open'].append(name)
            continue
        jobs['ended'] += 1
        if r['valid']:
            jobs['valid'] += 1
        else:
            jobs['invalid'].append(dict(job=name, why=r['why']))
    final = jobs['valid'] == jobs['expected'] and jobs['expected'] > 0
    fr = band_figures(groups, ramp, rng)
    newly = newly_covered(groups, [t for t in ramp])
    out = dict(
        round=cfg.get('round'), written=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=C.run, final=final, passed=passed if have else None,
        reason=verdict_reason(final, passed, have, jobs, f37, seeds, N),
        jobs=jobs,
        rule=dict(
            text='On the 37, on both seeds: forms covered of the refit arm minus the bundle arm is at least minus the noise band, and Ident-only forms of the refit arm minus the bundle arm is above 0. Sums are over the tasks whose 4 jobs are valid.',
            noise_band_definition='noise band = |forms covered by the bundle on seed 0 minus forms covered by the bundle on seed 1|, summed over the 37 tasks that have all 4 jobs valid',
            noise_band=N, per_seed=seeds),
        heldout37=f37,
        ramp22=dict(training_figures=True, note=RAMP_NOTE, figures=fr, newly_covered_tables=newly))
    chk = os.path.join(C.run, 'refit-check.json')
    if os.path.exists(chk):  # a round that the check stopped has a failed verdict, whose reason is the check's
        try:
            cs = json.load(open(chk))
        except ValueError:
            cs = {}
        if cs.get('status') in ('check failed', 'stopped at 60 s', 'check crashed'):
            out['passed'] = False
            out['stopped'] = cs['status']
            out['reason'] = 'round stopped, %s: %s; %s' % (cs['status'], (cs.get('verdict') or {}).get('reason', ''), out['reason'])
    print('\nVerdict (37 tasks counted %d of %d, noise band %d):' % (f37['tasks_counted'], f37['tasks_listed'], N))
    for s, v in f37['per_seed'].items():
        print('  seed %-5s forms covered bundle %d refit %d D %+d (%s); Ident-only bundle %d refit %d D %+d (%s)' % (
            s, v['forms_covered']['bundle'], v['forms_covered']['refit'], v['forms_covered']['D'], 'ok' if seeds[s]['forms_ok'] else 'below the band',
            v['ident_only']['bundle'], v['ident_only']['refit'], v['ident_only']['D'], 'up' if seeds[s]['ident_up'] else 'not up'))
    print('  mean of seeds D: forms covered %s, Ident-only %s' % (f37['mean_of_seeds']['forms_covered'], f37['mean_of_seeds']['ident_only']))
    print('  ramp22 (TRAINING figures of models-tk): tasks counted %d, newly covered tables %d' % (fr['tasks_counted'], len(newly)))
    print('  jobs: %d of %d valid, %d open, %d invalid; final %s; pass %s' % (jobs['valid'], jobs['expected'], len(jobs['open']), len(jobs['invalid']), final, out['passed']))
    Context.result = out
    Context.groups = groups


def main_jobs(specs):
    """The names arm_s<seed>/task of the lines of the main jobs (the arms bundle, refit, parity and refitcheck)."""
    return sorted('%s_s%d/%s' % (x['arm'], x['seed'], x['task']) for arm, lst in specs.items() if arm in MAIN_ARMS for x in lst)


def positives(groups, cfg):
    """The lines of the covered tables file: one per task and job of the arm refitp."""
    lines = []
    for (base, fold), by_seed in sorted(groups.items()):
        if base != 'refitp':
            continue
        for seed, by_task in sorted(by_seed.items()):
            for task, rec in sorted(by_task.items()):
                if not rec['ended']:
                    continue
                lines.append(task_line(task, SEED_NAME.get(seed, str(seed)), base, rec['work'], rec['rows']))
    return lines


def prepare(run, tasks_file, jobs_files):
    """Loads the task lists and the jobs files into Context, and makes the marker name of a job the file stem of the NODE_SCORE in its line: the read's validity rule and
    the parity script's checks both use that name."""
    C = Context
    C.run, C.cfg = run, json.load(open(tasks_file))
    C.specs = parse_jobs(jobs_files)
    C.want = expected_names(C.specs)
    original = ORIG_EXPECTED
    PA.expected_name = lambda arm: C.want[arm_of(arm)] if arm_of(arm) in C.want else original(arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('out')
    ap.add_argument('--returns')
    ap.add_argument('--ident')
    ap.add_argument('--gold')
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    res = {k: find_file(run, v, 'READ_' + k.upper()) for k, v in TASK_FILES.items()}
    if a.ident:
        res['ident'] = a.ident
    if a.gold:
        res['gold'] = a.gold
    jobs_files = find_jobs(run)
    for k in ('tasks', 'ident', 'gold'):
        if not res[k]:
            raise SystemExit('no %s file beside %s (looked for %s)' % (k, run, TASK_FILES[k]))
    if not jobs_files:
        raise SystemExit('no jobs file beside %s or in its kit tar' % run)
    C = Context
    prepare(run, res['tasks'], jobs_files)
    # the banks that the read loads once, kept for the covered rows
    orig_load = PA.load_bank

    def load_bank(path):
        bank = orig_load(path)
        C.last_bank.clear()
        C.last_bank[path] = bank
        return bank
    PA.load_bank = load_bank
    # the gold of the main tasks, with the positives' tasks where their gold file is present
    gold = json.load(open(res['gold']))
    if res['gold_n600'] and os.path.exists(res['gold_n600']):
        have = {x['task'] for x in gold}
        gold += [x for x in json.load(open(res['gold_n600'])) if x['task'] not in have]
    gold_path = os.path.join(tempfile.mkdtemp(prefix='refit-read-'), 'gold.json')
    json.dump(gold, open(gold_path, 'w'))
    os.environ.setdefault('READ_CACHE', os.path.join(run, 'read-cache.json'))
    # the number of jobs the read has to read: those not in the cache with the same file sizes
    cache = json.load(open(os.environ['READ_CACHE'])) if os.path.exists(os.environ['READ_CACHE']) else {}
    todo = 0
    for arm, task, folder in PA.job_folders(run):
        w = '%s/work/%s' % (folder, task)
        sig = [os.path.getsize(f) if os.path.exists(f) else -1 for f in (w + '.log', w + '.out.jsonl.bank', w + '.out.jsonl.picks', w + '.out.jsonl.cover')]
        todo += not (('%s/%s' % (arm, task)) in cache and cache['%s/%s' % (arm, task)]['sig'] == sig)
    C.todo, C.done, C.t0 = todo, 0, time.time()
    print('run %s: %d jobs to read, %d in the cache' % (run, todo, len(PA.job_folders(run)) - todo), flush=True)
    R.job_record = job_record
    R.verdict = verdict
    sys.argv = ['search_refit_read.py', run, res['ident'], gold_path]
    R.main()
    out = C.result
    # the covered rows hold the job folder: add it for the positives lines
    folders = {(arm, task): folder for arm, task, folder in PA.job_folders(run)}
    for (base, fold), by_seed in C.groups.items():
        for seed, by_task in by_seed.items():
            for task, rec in by_task.items():
                f = folders.get(('%s_s%d' % (base + ('f' if fold else ''), seed), task))
                if f:
                    rec['work'] = '%s/work/%s' % (f, task)
    ramp_rows = [row for s in PROMOTION_SEEDS for t in C.cfg['ramp22'] for row in (C.groups.get(('refit', False), {}).get(s, {}).get(t) or {}).get('rows', ())]
    lines = positives(C.groups, C.cfg)
    out_dir = os.path.dirname(os.path.abspath(a.out))
    ramp_path = os.path.join(out_dir, 'round2-positives.jsonl')
    covered_path = os.path.join(out_dir, 'covered-tables.jsonl')
    write_atomic(ramp_path, ''.join(json.dumps(dict(r, training_figure=True)) + '\n' for r in ramp_rows))
    write_atomic(covered_path, ''.join(json.dumps(x) + '\n' for x in lines))
    pos = [r for r in C.groups.get(('refitp', False), {}).values()]
    out['positives'] = dict(jobs_listed=len(C.specs.get('refitp', [])), jobs_read=sum(len(x) for x in pos), tasks_with_covered_rows=sum(1 for x in lines if x['covered']),
                            covered_rows=sum(len(x['covered']) for x in lines), file=covered_path)
    out['ramp22']['round2_positives_file'] = ramp_path
    out['ramp22']['round2_positives_rows'] = len(ramp_rows)
    write_atomic(a.out, json.dumps(out, indent=1) + '\n')
    print('wrote %s, %s (%d ramp rows), %s (%d task lines)' % (a.out, ramp_path, len(ramp_rows), covered_path, len(lines)))
    if a.returns:
        write_atomic(os.path.join(a.returns, 'verdict.json'), json.dumps(out, indent=1) + '\n')
        write_atomic(os.path.join(a.returns, 'covered-tables.jsonl'), ''.join(json.dumps(x) + '\n' for x in lines))
        write_atomic(os.path.join(a.returns, 'run.txt'), run + '\n')
        print('wrote verdict.json, covered-tables.jsonl and run.txt in %s' % a.returns)


ORIG_RECORD = R.job_record
ORIG_EXPECTED = PA.expected_name

def verdict_reason(final, passed, have, jobs, f37, seeds, band):
    """The reason line of a verdict: on a fail, each part of the rule that failed, with its figures; on a partial read, that it is partial."""
    head = '' if final else '%d of %d jobs valid, the verdict is partial; ' % (jobs['valid'], jobs['expected'])
    if not have:
        return head + 'no task of the 37 has all 4 jobs valid yet'
    if passed:
        return head + 'pass: forms covered within the noise band %d and Ident-only forms up on both seeds' % band
    parts = []
    for s, v in seeds.items():
        d = f37['per_seed'][s]
        if not v['forms_ok']:
            parts.append('seed %s forms covered D %+d, past the noise band %d' % (s, d['forms_covered']['D'], band))
        if not v['ident_up']:
            parts.append('seed %s Ident-only D %+d, not up' % (s, d['ident_only']['D']))
    return head + 'fail: ' + '; '.join(parts)


if __name__ == '__main__':
    main()
