"""Which programs of the union gold solve their task, on the current engine. A program fits when some assignment of its DETs gives every train output through its OUT query (each grid it gives is the output or the example's `alt` grid). It solves (test_ok) when it fits and, on each test example with an expected output, the fitting assignments give at most two distinct grids over all constraint models, and one is the expected output. Per task, each distinct program text of cases-SET.jsonl is run once. The fits go to fits-SET.jsonl in the gold-union folder, one line per task: task, and programs, a list of {text_sha, cases, assignments, fitting, fit, test_ok, why, sampler}. assignments counts the assignments of the OUT table, fitting those that give every train output, and why is the reason a program gives no tables (fit and test_ok are then null: no verdict). sampler is how the sampler's decoder takes the program, stepped with tables, under the settings of model/study/sampler/live_try.py (static pruning on): 'ok', or the refusal (sampler_outcome); 'not ended' and timeouts are no verdict. decode is whether the sampler's grammar takes it, with no table evaluated (sampler_decode), and decode_engine the engine that checked it. The union keeps a program when fit and test_ok, and neither sampler nor decode is a refusal.

  ARCLOG_IDENT_SOURCE=value PYTHONPATH=<site> python gold_union_fits.py SET [K N]    SET: train, dev or held-out; K N takes the tasks at positions K, K + N, ... and writes fits-SET-K.jsonl. A restart skips the tasks the file has. With FITS_TASKS set (tasks separated by spaces), K N name only the output file, and the run takes those tasks.
  With FITS_REUSE set (fits files separated by commas, with or without the header line), a program that has a row (same task and text_sha) in one of those files, the first that has it, is not run: its row copies that row's assignments, fitting, fit, test_ok and why, and its cases are those of the current cases-SET.jsonl. The progress line of each task says how many of its programs were copied.
  With FITS_CAP=S set, each program runs in a forked child that is killed after S seconds. A killed program has fit and test_ok null and why 'timeout S s', and the union leaves it out with that reason.
  Where the engine's replay of a program stops (the deadline, a cap), a later program of the task that has the same forms up to and with the form it stopped in (the identities of design.md, "Forms and tables") is not replayed in full: it runs for FITS_STOP_PROBE seconds (default 1), which gives its static refusals, and it gives `replay: stopped` as the first program did. See StopMemo.
  ARCLOG_IDENT_SOURCE=value PYTHONPATH=<site> python gold_union_fits.py SET decode K N     the same for decode, on an engine with Session.check_stream; it writes decode-SET-K.jsonl.
  ARCLOG_IDENT_SOURCE=value PYTHONPATH=<site> python gold_union_fits.py SET sampler K N     adds the sampler outcome to the programs of fits-SET.jsonl that have none: it writes sampler-SET-K.jsonl for the tasks at positions K, K + N, ..., and the merge takes it.
  ARCLOG_IDENT_SOURCE=value PYTHONPATH=<site> python gold_union_fits.py SET merge     writes fits-SET.jsonl from the fits-SET-K.jsonl files, sorted by task, after a first line {"t": "header", "code": {"sha", "dirty"}} (gold_union_code.py: the commit of the code that merged it). A reader of fits-SET.jsonl skips the lines that have `t`.
"""
import glob, hashlib, importlib.util, json, os, re, select, signal, sys, time
from pathlib import Path
from types import SimpleNamespace

import gold_union_code
sys.path.append(str(Path(__file__).resolve().parents[3]))  # model/study
import study_zst as Z  # the large files of OUT are zstd streams or plain files, whichever is on disk

ROOT = Path('/Users/davidlu/code/arc-workspace')
OUT = os.environ.get('GOLD_UNION_DIR', str(ROOT / 'work/lm/data-study/gold/gold-union')) + '/'  # GOLD_UNION_DIR: the folder of the inputs and outputs
WORK_CAP = int(os.environ.get('FITS_WORK_CAP', 1 << 28))  # the engine's table work cap; its default, 1 << 20, stops programs that the old runtime finished
DEADLINE = float(os.environ.get('FITS_DEADLINE', 120))  # the engine's deadline in seconds; its default, 10, stops programs by the machine's load
SESSION_BYTES = int(os.environ.get('FITS_SESSION_BYTES', 8 << 30))  # the engine's session byte bound; its default is 512 MiB
CAP = float(os.environ.get('FITS_CAP', 0))  # seconds per program; 0 runs each program in this process, with no cap
STOP_PROBE = float(os.environ.get('FITS_STOP_PROBE', 1))  # the engine's deadline in seconds for a program that a StopMemo holds as stopped: it still gets the engine's static checks, and gives no tables where it stops
SPLIT = {f[0]: 'held-out' if f[3] in ('held', 'held-out') else f[3] for f in (l.rstrip('\n').split('\t') for l in open(ROOT / 'model/study/samples/split_design/split2.tsv')) if f[0] != 'task'}  # {task: split}, from the `split` column


def set_of(t):
    """The split of the task: train, dev or held-out."""
    return SPLIT[t]


def sha16(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def engine():
    """(cli, arclog, numpy): scripts/arclog.py as a module, and the engine it runs on."""
    os.environ['ARCLOG_PY_INNER'] = str(ROOT)
    spec = importlib.util.spec_from_file_location('arclog_cli', ROOT / 'scripts/arclog.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    import arclog
    import numpy as np
    settings, evaluator = arclog.DecodeSettings, arclog.StudyTaskEvaluator
    arclog.DecodeSettings = lambda *a, **k: settings(*a, **{'table_work_cap': WORK_CAP, **k})
    arclog.StudyTaskEvaluator = lambda *a, **k: evaluator(*a, **{'session_bytes': SESSION_BYTES, **k})
    return cli, arclog, np


def programs_of(set_name):
    """{task: {text: [case]}} of the lines of cases-SET.jsonl that are not excluded, in the order of the file."""
    got = {}
    for l in Z.open_text(OUT + 'cases-%s.jsonl' % set_name):
        r = json.loads(l)
        if r['excluded'] in (True, 'True'):
            continue
        got.setdefault(r['task'], {}).setdefault(r['gold_sexp'], []).append(r['case'])
    return got


def parse(text):
    """The nested list of an s-expression."""
    stack = [[]]
    for tok in re.findall(r'[()]|[^\s()]+', text):
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return stack[0]


def sites_of(text):
    """[(relation name, site)] of the OUT query of a program, one for each site: the first selects the Position and the second the Color."""
    out = parse(re.search(r'^\(OUT .*$', text, re.M)[0])[0]
    return [('ex_input' if atom[0] == 'input' else atom[0], s) for atom in out[1:] for s in atom[1:]]


def column_of(names, site):
    """The column that a site selects: `^C` is the column C, `(:t ^V)` the field V of the record column t unless t is a column, `(:t (:V ^L))` the field V of t, and `(:C ^L)` the column C."""
    if isinstance(site, str):
        return site[1:]
    if isinstance(site[1], list):
        return '%s.%s' % (site[0][1:], site[1][0][1:])
    return site[0][1:] if site[0][1:] in names else '%s.%s' % (site[0][1:], site[1][1:])


def grids_of(tb, text):
    """{assignment: {example: [grid]}} of the OUT query: a grid is the sorted distinct [position, color] rows of one entry, or None where there is no grid. With two atoms a grid is the product of the Positions of the first atom's table and the Color of the second's, on the entries that agree on the DETs that both read and on the model."""
    (n1, s1), (n2, s2) = sites_of(text)[:2]
    t1, t2 = tb.find(n1), tb.find(n2)
    at = [tb.T['column_names'][t].index(column_of(tb.T['column_names'][t], s)) for t, s in ((t1, s1), (t2, s2))]

    def entries(t):
        """The entries of table t, an entry of the task (on no example) once for each example."""
        return [(e if e[0] != 'task' else (x,) + e[1:]) for e in tb.entries(t) for x in ([e[0]] if e[0] != 'task' else ['%s/%d' % (k, j) for k in ('train', 'test') for j in range(len(tb.task[k]))])]

    def column(t, c):
        ty = tb.T['column_types'][t][c]
        return [(ex, model, key, [tb.value(t, ty, r[c]) for r in raw]) for ex, model, key, raw, stop in entries(t)]

    by_key = {}
    if t1 == t2:
        ty = tb.T['column_types'][t1]
        for ex, model, key, raw, stop in entries(t1):
            g = sorted({(tuple(tb.value(t1, ty[at[0]], r[at[0]])), tb.value(t1, ty[at[1]], r[at[1]])) for r in raw})
            by_key.setdefault(key, {}).setdefault(ex, []).append([[list(p), c] for p, c in g])
        return by_key
    for ex, model, key, pos in column(t1, at[0]):
        for ex2, model2, key2, col in column(t2, at[1]):
            d1, d2 = {k[0]: k for k in key}, {k[0]: k for k in key2}
            if ex == ex2 and model == model2 and all(d1[r] == d2[r] for r in d1.keys() & d2.keys()):
                both = tuple(sorted({**d1, **d2}.values(), key=lambda k: k[0]))
                cs = set(col)
                g = sorted({(tuple(p), c) for p in pos for c in cs}) if len(cs) == 1 else None
                by_key.setdefault(both, {}).setdefault(ex, []).append(None if g is None else [[list(p), c] for p, c in g])
    return by_key


HEAD = re.compile(r'\((\w+) &([A-Za-z_]\w*)')
NAME = re.compile(r'&([A-Za-z_]\w*)((?:\.\w+)*)')


def form_idents(text):
    """[identity] of the forms of a program, in order of the text: as in design.md ("Forms and tables"), the form's text with each read replaced by the identity of the form it reads, and its own label dropped. The OUT query is no form."""
    ident, got = {}, []
    for x in text.splitlines():
        m = HEAD.match(x)
        if not m or x.startswith('(OUT'):
            continue
        body = NAME.sub(lambda n: '{%s}%s' % (ident[n[1]], n[2]) if n[1] in ident else '&_' + n[2], ' '.join(x[m.end():].split()))
        ident[m[2]] = hashlib.sha256((m[1] + body).encode()).hexdigest()[:16]
        got.append(ident[m[2]])
    return got


class StopMemo:
    """The programs of one task whose replay the engine stopped, by the forms they have up to the form it stopped in. The engine replays the forms in the order of the text and a form's table depends on the forms before it alone, so a program whose forms, up to and with the stopped form, have the same identities as those of a stopped program stops there too, under the same limits, and its replay is not run: it gives the same `replay: stopped`."""

    def __init__(self):
        self.stopped = []  # [tuple of identities, up to the stopped form]

    def hit(self, text):
        ids = form_idents(text)
        return any(ids[:len(p)] == list(p) for p in self.stopped)

    def add(self, text, form):
        self.stopped.append(tuple(form_idents(text)[:form + 1]))


def run_program(cli, arclog, np, text, task, tasks, task_json, deadline=None):
    """(tables, why, stop): what cli.run_case gives for a program text, and `stop`, the index of the form that the engine stopped in where its replay stopped and says so, else None. run_case does not return the engine's status, which says it. `deadline` is the engine's deadline in seconds, in place of DEADLINE."""
    settings = arclog.DecodeSettings()
    try:
        program = arclog.StudyProgram.from_sexp(text, settings)
    except ValueError as e:
        return None, 'refused: %s' % e, None
    evaluator = arclog.StudyTaskEvaluator(task, str(tasks.resolve()), settings)
    rows = 'held_rows' if 'held_rows' in type(evaluator).gold_tables.__text_signature__ else 'full_rows'  # as run_case does
    status, ct = evaluator.gold_tables(program, **{rows: True})
    st = json.loads(status)
    if st.get('status') not in (None, 'complete'):
        m = re.fullmatch(r'NodePath\(\[PathStep\((\d+)\)\]\)', str(st.get('form')))
        return None, 'replay: %s' % st.get('status'), int(m[1]) if m and st.get('status') == 'stopped' else None
    return cli.Tables(arclog, np, program, ct, task_json), None, None


def check(env, task, text, tasks, task_json, memo=None):
    """(assignments, fitting, test_ok, why) of a program text, as check_stop() gives it."""
    return check_stop(env, task, text, tasks, task_json, memo)[0]


def check_stop(env, task, text, tasks, task_json, memo=None):
    """((assignments, fitting, test_ok, why), stop) of a program text: the assignments of its OUT table, those that give every train output, whether the program solves (the fitting assignments give, on each test example, at most two distinct grids over all models, and one is the expected output), and the reason it gives no tables. `stop` is the index of the form the engine's replay stopped in, or None. With a StopMemo of the task, a program that it holds as stopped is not run (its stop is None, as the memo has it), and a program that stops is added to it."""
    cli, arclog, np = env
    held = memo is not None and memo.hit(text)
    try:
        tb, why, stop = run_program(cli, arclog, np, text, task, tasks, task_json, STOP_PROBE if held else None)
        if tb is None:
            if memo is not None and stop is not None and not held:
                memo.add(text, stop)
            return (0, 0, False, why[:200]), None if held else stop
        if not re.search(r'^\(OUT ', text, re.M):
            return (0, 0, False, 'no OUT form'), None
        by_key = grids_of(tb, text)
    except Exception as e:  # noqa: BLE001
        return (0, 0, False, '%s: %s' % (type(e).__name__, str(e)[:150])), None
    wants = {}

    def cells(g):
        h, w = len(g), len(g[0])
        return sorted([[r, h - 1 - r, c, w - 1 - c], g[r][c]] for r in range(h) for c in range(w))

    def want(ex):
        """The accepted grids of an example: its output, and its `alt` grid where the task gives one; None where it has no output."""
        if ex not in wants:
            kind, j = ex.split('/')
            e = task_json[kind][int(j)]
            wants[ex] = None if e.get('output') is None else [cells(e['output'])] + ([cells(e['alt']['grid'])] if e.get('alt') else [])
        return wants[ex]

    def gives(d, kind):
        exs = ['%s/%d' % (kind, j) for j in range(len(task_json[kind]))]
        return all(ex in d and all(g in want(ex) for g in d[ex]) for ex in exs if want(ex) is not None)

    def solves(fitting):
        """Whether, on each test example with an expected output, the fitting assignments give at most two distinct grids over all models, and one is an accepted grid."""
        for j in range(len(task_json['test'])):
            ex = 'test/%d' % j
            if want(ex) is not None:
                seen = {json.dumps(g) for d in fitting for g in d.get(ex, [])}
                if len(seen) > 2 or not seen & {json.dumps(g) for g in want(ex)}:
                    return False
        return bool(fitting)

    fitting = [d for d in by_key.values() if gives(d, 'train')]
    return (len(by_key), len(fitting), solves(fitting), None), None


def capped(env, task, text, tasks, task_json, memo=None):
    """check() in a forked child. A child still running after CAP seconds is killed. Its outcome is a timeout, not a verdict: assignments, fitting, fit and test_ok are null, and why is 'timeout'. The child gives its stop to the parent, which keeps it in the memo."""
    held = memo is not None and memo.hit(text)
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        with os.fdopen(w, 'w') as f:
            f.write(json.dumps(check_stop(env, task, text, tasks, task_json, memo)))
        os._exit(0)
    os.close(w)
    got, end = b'', time.time() + CAP
    while (left := end - time.time()) > 0 and select.select([r], [], [], left)[0]:
        chunk = os.read(r, 1 << 16)
        if not chunk:
            break
        got += chunk
    else:
        os.kill(pid, signal.SIGKILL)
    os.close(r)
    os.waitpid(pid, 0)
    if not got:
        return None, None, None, 'timeout %ds' % CAP
    result, stop = json.loads(got)
    if memo is not None and stop is not None and not held:
        memo.add(text, stop)
    return tuple(result)


def sampler_settings():
    """The decode settings of the sampler: SETTINGS of model/study/sampler/live_try.py, read from its text (importing it loads the sampler)."""
    import ast
    tree = ast.parse(Path(os.environ.get('SAMPLER_LIVE_TRY') or ROOT / 'model/study/sampler/live_try.py').read_text())  # SAMPLER_LIVE_TRY: another live_try.py, for one whose SETTINGS is no constant dict(...)
    node = next(n.value for n in tree.body if isinstance(n, ast.Assign) and [t.id for t in n.targets if isinstance(t, ast.Name)] == ['SETTINGS'])
    return eval(compile(ast.Expression(node), 'live_try.py', 'eval'), {'__builtins__': {}, 'dict': dict})  # a dict(...) of constants


def sampler_outcome(env, task_json, text):
    """How the sampler's decoder takes the program: 'ok' where every token steps and the decoder ends, else 'refused: <reason>', 'does not parse: <reason>' or 'not ended'. It decodes as live_try.py does: an open-world session of the task with no test output, the sampler's settings, and a 2 GiB session bound."""
    _, arclog, _ = env
    d = json.loads(json.dumps(task_json))
    for t in d['test']:
        t.pop('output', None)
    sess = arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), arclog.DecodeSettings(**SAMPLER), session_bytes=2 << 30)
    try:
        ids, model, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    except ValueError as e:
        return 'does not parse: %s' % str(e)[:150]
    dec = sess.decoder()
    try:
        for t, m in zip(ids, model):
            if m:
                dec.step(t)
    except (arclog.Refusal, arclog.Fault) as e:
        return 'refused: %s' % str(e)[:150]
    return 'ok' if dec.ended else 'not ended'  # the sampler's 10 s deadline stops the decoder without a refusal, so under load this is no verdict


SAMPLER = sampler_settings()
SAMPLER_CAP = float(os.environ.get('SAMPLER_CAP', 60))  # seconds per program for sampler_outcome; a program past it is 'timeout'
SAMPLER_TASK_CAP = float(os.environ.get('SAMPLER_TASK_CAP', 180))  # seconds per task for sampler_run; the programs left after it are 'timeout: task cap', not counted


def sampler_capped(env, task_json, text):
    """sampler_outcome() in a forked child that is killed after SAMPLER_CAP seconds: then 'timeout <cap>s', a count not made."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        with os.fdopen(w, 'w') as f:
            f.write(sampler_outcome(env, task_json, text))
        os._exit(0)
    os.close(w)
    got, end = b'', time.time() + SAMPLER_CAP
    while (left := end - time.time()) > 0 and select.select([r], [], [], left)[0]:
        chunk = os.read(r, 1 << 16)
        if not chunk:
            break
        got += chunk
    else:
        os.kill(pid, signal.SIGKILL)
    os.close(r)
    os.waitpid(pid, 0)
    return got.decode() if got else 'timeout %ds' % SAMPLER_CAP


def sampler_decode(env, task_json, text):
    """Whether the sampler's grammar takes the program, with no table evaluated: 'ok', 'refused: <reason> at token <i>' or 'does not parse: <reason>', from the engine's Session.check_stream under the sampler's settings; None on an engine without it. It can't give the refusals that need evaluation (DetAdmission, and the decode having ended), so a program refused only for those shows 'ok'."""
    _, arclog, _ = env
    d = json.loads(json.dumps(task_json))
    for t in d['test']:
        t.pop('output', None)
    sess = arclog.Session(arclog.Task.from_json(json.dumps(d), arclog.World.Open), arclog.DecodeSettings(**SAMPLER), session_bytes=2 << 30)
    if not hasattr(sess, 'check_stream'):
        return None
    try:
        ids, model, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    except ValueError as e:
        return 'does not parse: %s' % str(e)[:150]
    got = sess.check_stream(ids, model)
    return 'ok' if got is None else 'refused: %s at token %d' % (str(got[1])[:150], got[0])


def engine_name(env):
    """The folder that names the engine: the site-* or runtime-* folder that holds the arclog package."""
    parts = Path(env[1].__file__).parts
    return next((x for x in reversed(parts) if x.startswith(('site-exp', 'runtime-'))), parts[-3])


def reuse_of():
    """{task: {text_sha: program}} of the files of FITS_REUSE, the first file that has a program in place of a later one."""
    got = {}
    for p in filter(None, os.environ.get('FITS_REUSE', '').split(',')):
        for r in rows_of(p):
            for x in r['programs']:
                got.setdefault(r['task'], {}).setdefault(x['text_sha'], x)
    return got


def one(env, task, texts, tasks, reuse):
    """(the fits row of a task, how many of its programs it copies). `reuse` is {text_sha: program} of the task, from reuse_of()."""
    task_json = json.load(open(tasks / (task + '.json')))
    progs, copied, memo = [], 0, StopMemo()
    for text, cases in texts.items():
        old = reuse.get(sha16(text))
        if old:
            progs.append(dict(text_sha=old['text_sha'], cases=cases, **{k: old[k] for k in ('assignments', 'fitting', 'fit', 'test_ok', 'why')},
                              sampler=old.get('sampler') or sampler_capped(env, task_json, text),
                              **decode_of(env, task_json, text, old)))
            copied += 1
            continue
        n, k, ok, why = (capped if CAP else check)(env, task, text, tasks, task_json, memo)
        progs.append(dict(text_sha=sha16(text), cases=cases, assignments=n, fitting=k, fit=None if why else k > 0, test_ok=None if why else ok, why=why,
                          sampler=sampler_capped(env, task_json, text), **decode_of(env, task_json, text, {})))
    return dict(task=task, programs=progs), copied


def decode_of(env, task_json, text, old):
    """{decode, decode_engine} of the program: the old row's, or sampler_decode() on this engine where it has the call; else {}."""
    if old.get('decode'):
        return dict(decode=old['decode'], decode_engine=old.get('decode_engine'))
    got = sampler_decode(env, task_json, text)
    return dict(decode=got, decode_engine=engine_name(env)) if got else {}


def sampler_run(set_name, k, n, field='sampler'):
    """Writes FIELD-SET-K.jsonl: {task, text_sha, FIELD} of each program of fits-SET.jsonl with no FIELD, for the tasks at positions K, K + N, ... FIELD is sampler (sampler_capped, under SAMPLER_TASK_CAP per task) or decode (sampler_decode, with decode_engine). A restart skips the tasks the file has."""
    texts = {t: {sha16(x): x for x in v} for t, v in programs_of(set_name).items()}
    rows = [r for r in rows_of(OUT + 'fits-%s.jsonl' % set_name) if r['task'] in texts]
    if os.environ.get('FITS_TASKS'):  # tasks separated by spaces, in place of every task
        rows = [r for r in rows if r['task'] in os.environ['FITS_TASKS'].split()]
    mine = [r for i, r in enumerate(sorted(rows, key=lambda r: r['task'])) if i % n == k]
    path = OUT + '%s-%s-%d.jsonl' % (field, set_name, k)
    done = {json.loads(l)['task'] for l in Z.open_text(path) if l.endswith('\n')} if Z.exists(path) else set()
    env, start = engine(), time.time()
    with Z.open_text(path, 'a') as f:
        for i, r in enumerate(mine, 1):
            if r['task'] in done:
                continue
            task_json = json.load(open(ROOT / 'data/tasks' / (r['task'] + '.json')))
            got, end = [], time.time() + SAMPLER_TASK_CAP
            for x in r['programs']:
                if not x.get(field) and x['text_sha'] in texts[r['task']]:
                    text = texts[r['task']][x['text_sha']]
                    if field == 'decode':
                        got.append(dict(task=r['task'], text_sha=x['text_sha'], decode=sampler_decode(env, task_json, text), decode_engine=engine_name(env)))
                    else:
                        out = sampler_capped(env, task_json, text) if time.time() < end else 'timeout: task cap %ds, not counted' % SAMPLER_TASK_CAP
                        got.append(dict(task=r['task'], text_sha=x['text_sha'], sampler=out))
            f.write(''.join(json.dumps(g) + '\n' for g in got) or json.dumps({'task': r['task'], 'text_sha': None, field: None}) + '\n')
            f.flush()
            el = time.time() - start
            print('%s %d/%d  refused %d/%d  %.0fs  eta %.0fs' % (r['task'], i, len(mine), sum(g[field] != 'ok' for g in got), len(got), el, el / i * (len(mine) - i)), flush=True)


def shard_files(set_name):
    return Z.glob(OUT + 'fits-%s-*.jsonl' % set_name)


def rows_of(path):
    """The task rows of a fits file, whole lines only, less its header line."""
    for l in Z.open_text(path):
        if l.endswith('\n'):
            r = json.loads(l)
            if r.get('t') != 'header':
                yield r


def merge(set_name):
    got, outcome = {}, {}
    for field in ('sampler', 'decode'):  # outcomes that sampler_run added to older rows
        for p in Z.glob(OUT + '%s-%s-*.jsonl' % (field, set_name)):
            for l in Z.open_text(p):
                if l.endswith('\n'):
                    s = json.loads(l)
                    if s.get(field):
                        outcome.setdefault((s['task'], s['text_sha']), {}).update({k: v for k, v in s.items() if k not in ('task', 'text_sha')})
    for p in shard_files(set_name):
        for r in rows_of(p):
            for x in r['programs']:
                if x['why']:  # an older run wrote false here
                    x.update(fit=None, test_ok=None)
                for f, v in outcome.get((r['task'], x['text_sha']), {}).items():
                    if not x.get(f):
                        x[f] = v
            got[r['task']] = json.dumps(r) + '\n'
    if got:
        with Z.open_text(OUT + 'fits-%s.jsonl' % set_name, 'w', atomic=True) as f:
            f.write(gold_union_code.header() + ''.join(got[t] for t in sorted(got)))
    print(len(got), 'tasks')


def run(set_name, shard=None):
    k, n = shard or (0, 1)
    todo = programs_of(set_name)
    mine = [t for i, t in enumerate(sorted(todo)) if i % n == k]
    if os.environ.get('FITS_TASKS'):  # tasks separated by spaces, in place of the shard's own
        mine = [t for t in os.environ['FITS_TASKS'].split() if t in todo]
    path = OUT + ('fits-%s-%d.jsonl' % (set_name, k) if shard else 'fits-%s.jsonl' % set_name)
    done = {r['task'] for r in rows_of(path)} if Z.exists(path) else set()
    Z.trim_to_last_newline(path)  # a killed run may leave half a line
    left = [t for t in mine if t not in done]
    env, tasks, reuse = engine(), ROOT / 'data/tasks', reuse_of()
    rest, fit, seen, start = sum(len(todo[t]) for t in left), 0, 0, time.time()
    with Z.open_text(path, 'a') as f:
        for i, t in enumerate(left, len(mine) - len(left) + 1):
            row, copied = one(env, t, todo[t], tasks, reuse.get(t, {}))
            f.write(json.dumps(row) + '\n')
            f.flush()
            fit += sum(bool(p['fit']) for p in row['programs'])
            seen += len(row['programs'])
            el = time.time() - start
            print('%s %d/%d  programs fit %d/%d  reused %d/%d  %.0fs  eta %.0fs' % (t, i, len(mine), fit, seen, copied, len(row['programs']), el, el / seen * (rest - seen)), flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[1:] == ['merge']:
        merge(a[0])
    elif a[1:2] in (['sampler'], ['decode']):
        sampler_run(a[0], int(a[2]), int(a[3]), a[1])
    else:
        run(a[0], (int(a[1]), int(a[2])) if a[2:] else None)
