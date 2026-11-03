"""At each INIT pick of form-set.jsonl, the components of the walk's list whose result is nonempty on the task's own data, for the labels that gold's ports bind.

  census_env.sh component_feasible.py [--limit N]

Writes component-rows.jsonl in this folder: one row per pick as soon as it is read, flushed. A rerun skips the picks that have a row. It prints a rate and an ETA.

Definitions, fixed before any held row was read:

- The list: the components that Run.init draws from at this pick: pri['comps'] with an entry in pri['comp_ports'], that the vocabulary holds and that the decoder admits after the INIT token, over every form before the INIT.
- A bound port of gold: one port of gold's rewritten INIT, with its body and its head. Its head columns are its groups: one label, or the labels of a record. Only labels that a head names count as bound; a label that a body makes and no head names does not.
- A trial for component C: each port of C takes one bound port of gold or is left out. A port of C that takes a bound port has every column other than `key` filled by a distinct group of that port's head. A column of a fixed type takes a one-label group; a column of a type parameter takes any group. A body that two ports of C use has its labels renamed in the second use. Gold's key body stays as it is. A port with a `key` column whose body reads a key label stands in the key group, and any other port stands after it, as a port that reads no key does in Run.init.
- Types: the decoder judges them: a trial that StudyProgram.from_sexp or a step refuses is refused. To keep the trials under the cap, an option is left out before any trial where the group is one label, the label's type is known from the bound port's table, and the column's type is fixed and its family, as Run.head_need gives it, does not hold that type.
- A component with a port that gold's form does not bind: that port is left out, and the decoder decides whether the form is legal without it. A required port that no bound port can fill therefore ends as refused. A component where no port can take a bound port is no_binding, with no trial.
- Where gold has a key and every trial with the key is refused, C is tried with no key, each body taking the key labels as labels of its own.
- Trials go from most ports bound to fewest, at most CAP per component and COMPONENT_SECONDS of trial time, and stop at the first trial with rows on every input. A table request ends at TABLE_SECONDS (a session setting); a trial that ends so counts as incomplete.
- Gold's own component has one trial: gold's form.
- Result: the rows of the form's relations that have a column, by step_tables after the form closes, on each train and test input of the task. A relation with no column is a flag that holds no value, and does not count. A trial has `rows_some` where one relation has a row on one input, which is the bar of the walk's own `try:empty` gate, and `rows_all` where every input has a row in one relation or another.
- Status of C: rows_all, rows_some, empty, incomplete (a table past a work cap or a fault, and no trial with rows), refused, no_binding.

Values: for each relation of the kept trial its labels, types, row count per input and the first SAMPLE rows of the first two inputs that have rows. `ports` gives the same for each bound port of gold, read from a RULE of its body.
"""
import argparse
import hashlib
import itertools
import json
import os
import re
import sys
import time

os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
sys.path.insert(0, os.environ['ARC_ROOT'] + '/work/lm/data-study/gold/form-anatomy-top-tenth')
import arclog  # noqa: E402
import body_extract as X  # noqa: E402
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402
import search_gold as G  # noqa: E402
import superdag as D  # noqa: E402
from sample2_col import parse_table  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ROOT = os.environ['ARC_ROOT']
ENGINE_SO = ROOT + '/work/lm/data-study/ast/run/runtime-ba0754492/py313-path/arclog/arclog.abi3.so'
SO_SHA256_16 = '4538e2630f39d751'
CAP = 256
TABLE_SECONDS = 2.0  # the session's deadline_seconds here, in place of the walk's
COMPONENT_SECONDS = 6.0
SAMPLE = 6
KEY = 'key'


def session(task):
    return arclog.Session(arclog.Task.from_json(open('%s/data/tasks/%s.json' % (ROOT, task)).read(), arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))


def stream(sess, text):
    i, m, _ = arclog.StudyProgram.from_sexp(text, sess.settings).decode_stream()
    return [int(x) for x in i], [int(bool(x)) for x in m]


def normal_lines(row):
    ls = list(row['lines'])
    for i, new in sorted(row['replace'], key=lambda x: -x[0]):
        ls[i:i + 1] = new
    sess = session(row['task'])
    norm = arclog.StudyProgram.from_stream(sess, *stream(sess, '\n'.join(ls))).sexp()
    return [x for x in norm.splitlines() if x.strip()]


def parse_init(text):
    """(head, component, key atoms or None, [port]) of an INIT's text; a port has name, head, atoms and whether gold has it in the key group."""
    p = X.parse(text)
    head, comp, ports, key = p[1], p[2], [], None
    for e in p[3:]:
        if e[0] == KEY:
            key = e[1]
            for q in e[2:]:
                ports.append(dict(name=q[0], head=q[1], atoms=q[2:], inside=True))
        else:
            ports.append(dict(name=e[0], head=e[1], atoms=e[2:], inside=False))
    keys = {lab for m, lab in X.occurrences(key) if m == '^'} if key else set()
    for q in ports:
        q['groups'] = [(g[0][1:], g[1:]) for g in q['head']]
        q['reads_key'] = bool(keys & {lab for _, lab in X.occurrences(q['atoms'])})
        q['made'] = {lab for m, lab in X.occurrences(q['atoms']) if m == '*'}
    return head, comp, key, ports, keys


def renamed(x, names):
    if isinstance(x, list):
        return [renamed(y, names) for y in x]
    m = X.LABEL.match(x)
    return m[1] + names[m[2]] if m and m[2] in names else x


def family(pri, t):
    return live.HEAD_FITS.get(t) or next((set(x) for x in pri['families'] if t in x), {t})


def fixed(t, params):
    return t not in params or t == 'Point'


def type_clash(pri, t, grp, params, types):
    """Whether a fixed column of type t cannot take the group, from the labels' types."""
    if not fixed(t, params):
        return False
    if len(grp) != 1 or isinstance(grp[0], list):
        return True
    have = types.get(grp[0])
    return have is not None and have not in family(pri, t)


def port_options(pri, cols, params, gold):
    """Each way port cols of a component can take a bound port of gold: (index in gold, [(column, group)])."""
    rest = [(c, t) for c, t in cols if c != KEY]
    out, seen = [], set()
    for gi, g in enumerate(gold):
        groups = g['groups']
        if not rest:
            ways = [()]
        else:
            ways = itertools.permutations(range(len(groups)), len(rest))
        for way in ways:
            m = [(c, groups[k][1]) for (c, t), k in zip(rest, way)]
            if any(type_clash(pri, t, groups[k][1], params, g['types']) for (c, t), k in zip(rest, way)):
                continue
            sig = (gi, X.show([[c, *grp] for c, grp in m]))
            if sig not in seen:
                seen.add(sig)
                out.append((gi, m))
    return out


def trials(pri, ports, params, gold):
    """Assignments of the component's ports, most ports bound first: tuples with one option or None per port."""
    opts = [port_options(pri, cols, params, gold) for _, cols in ports]
    idx = [i for i, o in enumerate(opts) if o]
    for k in range(len(idx), 0, -1):
        for sub in itertools.combinations(idx, k):
            for pick in itertools.product(*[opts[i] for i in sub]):
                a = [None] * len(ports)
                for i, o in zip(sub, pick):
                    a[i] = o
                yield a


def form_text(head, comp, key, keys, ports, gold, assign, unkeyed=False):
    """The text of the INIT of comp with the assignment, or None where a rename cannot apply."""
    used, inside, outside = {}, [], []
    for (name, cols), a in zip(ports, assign):
        if a is None:
            continue
        gi, m = a
        g = gold[gi]
        n = used.get(gi, 0)
        used[gi] = n + 1
        names = {lab: '%sZ%d' % (lab, n) for lab in g['made']} if n else {}
        atoms = renamed(g['atoms'], names)
        hd = [[':' + c, *renamed(grp, names)] for c, grp in m]
        if key is not None and unkeyed:
            atoms = X.remark(atoms)
        text = '(%s %s %s)' % (name, X.show(hd) if hd else '()', ' '.join(X.show(x) for x in atoms))
        has_key = any(c == KEY for c, _ in cols)
        (inside if key is not None and not unkeyed and has_key and g['reads_key'] else outside).append(text)
    if not inside and not outside:
        return None
    if key is not None and not unkeyed:
        group = '(key %s %s)' % (X.show(key), ' '.join(inside))
        return '(INIT %s %s %s %s)' % (head, comp, group, ' '.join(outside))
    return '(INIT %s %s %s)' % (head, comp, ' '.join(outside))


def read_form(dec, before, sess, scope, text):
    """(status, tables). status: refused, incomplete or ok; tables: [dict(rel, labels, types, inputs, sample)]."""
    try:
        ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
        toks = [int(t) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
        f = dec.fork()
        for t in toks:
            f.step(t)
        ct = arclog.step_tables(f, *live.TABLES, True, before)
    except Exception as e:  # noqa: BLE001  # a refused text or a refused step is a result of the trial
        return 'refused', re.sub(r'\d+', 'N', '%s: %s' % (type(e).__name__, str(e)))[:160]
    tabs, bad = [], None
    if not D.relation_tables(ct):
        return 'incomplete', ([], 'no table: the request ran to the deadline')
    for slot, j in D.relation_tables(ct):
        try:
            tb = parse_table(D.OneTable(ct, j))
        except Exception as e:  # noqa: BLE001  # a fault, or an entry past a cap
            bad = re.sub(r'\d+', 'N', str(e))[:160]
            continue
        entries = [(list(ex), rows) for ex, _, rows, _, _ in tb['entries']]
        some = [(ex, rows) for ex, rows in entries if rows][:2]
        tabs.append(dict(slot=slot, labels=[str(x) for x in tb['labels']], types=[str(x) for x in tb['types']], inputs=[[*ex, len(rows)] for ex, rows in entries], sample=[[ex, [list(map(int, r)) for r in sorted(rows)[:SAMPLE]]] for ex, rows in some]))
    return ('incomplete' if bad and not any(i[2] for t in tabs for i in t['inputs']) else 'ok'), (tabs, bad)


def judge(tabs, inputs):
    """rows_all, rows_some or empty, from the tables of a trial: a relation with no column does not count."""
    have = {tuple(i[:2]) for t in tabs if t['types'] for i in t['inputs'] if i[2]}
    if not have:
        return 'empty'
    return 'rows_all' if inputs <= have else 'rows_some'


RANK = dict(rows_all=4, rows_some=3, empty=2, incomplete=1, refused=0)


def read_component(pri, comp, gold_comp, target, head, key, keys, gold, ports, params, dec, before, sess, scope, inputs):
    out = dict(trials=0, refused=0, capped=False, unkeyed=False)
    best = None

    start = time.time()

    def trial(text, unkeyed=False):
        nonlocal best
        out['trials'] += 1
        status, got = read_form(dec, before, sess, scope, text)
        if status == 'refused':
            out['refused'] += 1
            out.setdefault('why', got)
            return False
        tabs, bad = got
        st = 'incomplete' if status == 'incomplete' else judge(tabs, inputs)
        if best is None or RANK[st] > RANK[best['status']]:
            best = dict(status=st, text=text, tables=tabs, unkeyed=unkeyed, table_note=bad)
        return st == 'rows_all'

    if comp == gold_comp:
        trial(target)
    else:
        any_way = False
        for unkeyed in ([False, True] if key is not None else [False]):
            done = False
            for a in trials(pri, ports, params, gold):
                any_way = True
                if out['trials'] >= CAP or time.time() - start >= COMPONENT_SECONDS:
                    out['capped'] = True
                    break
                try:
                    text = form_text(head, comp, key, keys, ports, gold, a, unkeyed)
                except X.Unsafe:
                    continue
                if text and trial(text, unkeyed):
                    done = True
                    break
            if done or best is not None or out['capped']:
                break
        if not any_way:
            out['status'] = 'no_binding'
            return out
    if best is None:
        out['status'] = 'refused'
    else:
        out.update(best)
    return out


def label_types(g, tabs):
    """{label of g's head: its type}, where the body names the label at one column and the bound port's table has that column."""
    out = {}
    if not tabs:
        return out
    by_col = dict(zip(tabs[0]['labels'], tabs[0]['types']))
    text = ' '.join(X.show(a) for a in g['atoms'])
    for _, grp in g['groups']:
        for lab in grp:
            if isinstance(lab, list):
                lab = lab[-1]
            cols = set(re.findall(r'\(:(\S+) [*^]?%s\)' % re.escape(lab), text))
            if len(cols) == 1 and cols <= set(by_col):
                out[lab] = by_col[cols.pop()]
    return out


def port_values(dec, before, sess, scope, gold):
    """The rows of each bound port of gold, from a RULE of its body with the key labels as labels of its own. Sets each port's `types`."""
    out = []
    for g in gold:
        g['types'] = {}
        row = dict(port=g['name'], head=X.show(g['head']))
        try:
            text = '(RULE &zz_port %s)' % ' '.join(X.show(a) for a in X.remark(g['atoms']))
            status, got = read_form(dec, before, sess, scope, text)
        except X.Unsafe as e:
            status, got = 'refused', str(e)
        row['status'] = status
        if status == 'refused':
            row['why'] = got
        else:
            row['tables'] = got[0]
            g['types'] = label_types(g, got[0])
            row['label_types'] = g['types']
        out.append(row)
    return out


def done_keys(path):
    got = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                got.add(json.loads(line)['key'])
            except json.JSONDecodeError:
                pass
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    ap.add_argument('--out', default=HERE + 'component-rows.jsonl')
    a = ap.parse_args()
    so = hashlib.sha256(open(ENGINE_SO, 'rb').read()).hexdigest()
    if not so.startswith(SO_SHA256_16):
        sys.exit('arclog .so is %s; the census manifest has %s' % (so, SO_SHA256_16))
    rows = [json.loads(x) for x in open(HERE + 'form-set.jsonl')]
    done = done_keys(a.out)
    todo = [r for r in rows if r['key'] not in done]
    print('%d picks, %d done, %d to do' % (len(rows), len(done), len(todo)), flush=True)
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    pri = sampler.pri
    live_try.SETTINGS = dict(live_try.SETTINGS, deadline_seconds=TABLE_SECONDS)
    t0, spent = time.time(), 0
    with open(a.out, 'a') as out:
        for r in todo[:a.limit]:
            t1 = time.time()
            nl = normal_lines(r)
            i, scope, target = r['index'], None, None
            scope, target = nl[:i], nl[i]
            assert target == r['target'], r['key']
            sess, task_json, _ = live_try.session_of(r['task'])
            run = or_q.GuidedRun(pri, sess, time.monotonic() + 3600, task_json, live.Limits(form_tries=1))
            dec, pg = run.scope(scope)
            f = run.open_form(pg, dec, 'INIT')
            names = [c for c in pri['comps'] if c in run.tok and c in pri['comp_ports']]
            names = [c for c, y in zip(names, f.admits([run.tok[c] for c in names])) if y]
            head, gold_comp, key, gold, keys = parse_init(target)
            before = pg.before
            status, got = read_form(dec, before, sess, scope, target)
            assert status != 'refused', (r['key'], got)
            inputs = {tuple(x[:2]) for t in got[0] for x in t['inputs'] if x[0] in (1, 2)} or {tuple(x[:2]) for t in got[0] for x in t['inputs']}
            port_rows = port_values(dec, before, sess, scope, gold)
            comps = {}
            for c in names:
                t2 = time.time()
                params, ports = pri['comp_ports'][c]
                comps[c] = read_component(pri, c, gold_comp, target, head, key, keys, gold, ports, params, dec, before, sess, scope, inputs)
                comps[c]['seconds'] = round(time.time() - t2, 3)
            earlier = [m[1] for x in scope for m in [re.match(r'\(INIT \S+ (\w+)', x)] if m]
            row = dict(key=r['key'], task=r['task'], form=r['form'], held=r['held'], gold_component=gold_comp, keyed=key is not None, listed=names, inputs=sorted(inputs), components=comps, ports=port_rows, earlier_gold_components=earlier, scope_lines=i, seconds=round(time.time() - t1, 2))
            out.write(json.dumps(row) + '\n')
            out.flush()
            spent += 1
            rate = (time.time() - t0) / spent
            st = [c for c, v in comps.items() if v.get('status') in ('rows_all', 'rows_some')]
            print('%s held=%s gold %s %s: %d of %d have rows; %d trials (%.1f s); %.2f s per pick, %d left, ETA %.0f s' % (r['key'], r['held'], gold_comp, comps[gold_comp].get('status'), len(st), len(names), sum(v['trials'] for v in comps.values()), row['seconds'], rate, len(todo) - spent, rate * (len(todo) - spent)), flush=True)


if __name__ == '__main__':
    main()
