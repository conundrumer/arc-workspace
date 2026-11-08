"""Dev labeling layer: whether the feature library tells a broken query from a correct one. Not model input.

    <runtime python> -I -B breaks.py run TASK OUT_DIR VARIANTS_DIR [N_PAIRS [SELECT]]
    <runtime python> -I -B breaks.py score OUT_DIR TASK [TASK ...]

run: makes the task's broken programs, each the solver with one edit: a negation dropped, a comparison turned around or made strict or not,
smallest and largest or rank and the opposite rank traded, inside and interior traded, a branch of an OR dropped, or, in a form that
determines a task parameter, a proposer replaced by another with the same columns in the lib registry. Where the first branch is dropped, the
branch that becomes first makes each label that the dropped branch exported, at its first site or `=` that names it. An edit that the reader
rejects is an illegal program, and is not scored. A program with an edit in a form that determines a task parameter has that parameter free:
it runs with the other proposer values pinned, and gives one record `<edit id>@<n>` per assignment of its parameters, the first
MAX_ASSIGNMENTS of them. The new pairs are up to N_PAIRS input variants of VARIANTS_DIR/<task>.variants.jsonl (none, and no read of VARIANTS_DIR, where N_PAIRS is 0)
that meet the preconditions of every table on the way to the output (analyze.valid_input), or, with SELECT `any`, any input variants, each
with the solver's output on it from the table cache. The solver and each broken program run on the task with the new pairs added as train pairs, at the task's own proposer values. Writes
OUT_DIR/<task>.breaks.jsonl: a record of the new pairs, then one record per program with its outputs, the row digests and the features of its
tables at every example. A restart skips the programs already written. OUT_DIR/<task>.started lists each program before it runs; a restart
writes an error record for a program that an earlier run began and did not finish, such as one stopped by a cap on memory, and skips it.

score: takes each program's postconditions over the task's own examples, and counts:
- a broken program: its output differs from the solver's at some example; a program whose outputs are the solver's everywhere is equivalent,
  and is not scored;
- a broken table: a table of the edited form of a broken program whose rows differ from the solver's table of that name at some example,
  while every table it reads has the solver's rows at every example (`judged`): the edited query on correct inputs. A table that changes
  and is not judged reads a changed table or stands outside the edited form; it is counted apart, and not scored;
- shown on the train pairs: a broken table whose postconditions differ from those of the solver's table of that name;
- flagged on a new pair: a table with a postcondition that fails at a new pair where the postconditions of the tables upstream of it hold.
A correct table (a table of the solver) that is flagged is a false alarm. Per family of features (growth.FAMILIES), the broken and the correct
tables that a postcondition of the family flags.
"""
import copy
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'features'))
import analyze as A  # noqa: E402
import jsonl as J  # noqa: E402

PARAMETER_FORMS = ('DET', 'DET_OR_RULE', 'RULE_OR_DET', 'RIGID_DET')
MAX_ASSIGNMENTS = 8
import paths  # noqa: E402

REGISTRY = paths.REGISTRY
BARE_COLUMN_TYPES = {'C': 'Color', 'N': 'Nat', 'A': 'Axis', 'C_from': 'Color', 'C_to': 'Color'}  # columns the registry gives without a type
TURN = {'!=': '=', '=': '!=', '<': '>', '>': '<', '<=': '>=', '>=': '<='}
STRICT = {'<': '<=', '<=': '<', '>': '>=', '>=': '>'}
READER = re.compile(r"files do not read|does not read|got 'NoneType'")  # the reader rejected the edited program
TRADE = {'minimal': 'maximal', 'maximal': 'minimal', 'rank': 'dual_rank', 'dual_rank': 'rank', 'inside': 'interior', 'interior': 'inside'}


def code_mask(text):
    """For each character, whether it is code: not in a comment or a string."""
    mask, i, n = [True] * len(text), 0, len(text)
    while i < n:
        if text[i] == ';':
            while i < n and text[i] != '\n':
                mask[i] = False
                i += 1
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            for k in range(i, min(j + 1, n)):
                mask[k] = False
            i = j + 1
        else:
            i += 1
    return mask


def close_of(text, mask, i):
    """The index of the parenthesis that closes the one at i."""
    depth = 0
    for j in range(i, len(text)):
        if mask[j] and text[j] == '(':
            depth += 1
        elif mask[j] and text[j] == ')':
            depth -= 1
            if depth == 0:
                return j
    raise ValueError('unbalanced at %d' % i)


def top_forms(text, mask):
    """(start, end, head) of each top-level form."""
    out, i = [], 0
    while i < len(text):
        if mask[i] and text[i] == '(':
            j = close_of(text, mask, i)
            out.append((i, j + 1, text[i + 1:j].split(None, 1)[0]))
            i = j + 1
        else:
            i += 1
    return out


def children(text, mask, i):
    """(start, end) of each list inside the form that opens at i."""
    out, j, end = [], i + 1, close_of(text, mask, i)
    while j < end:
        if mask[j] and text[j] == '(':
            k = close_of(text, mask, j)
            out.append((j, k + 1))
            j = k + 1
        else:
            j += 1
    return out


def exporting(first, rest, branch):
    """branch, made to make each label that the branch first exports: one it makes and every branch of rest names. The first site or `=` in
    branch that names such a label makes it."""
    bare = lambda L: re.compile(r'(?<![\w*^:&.])%s(?!\w)' % re.escape(L))
    for L in dict.fromkeys(re.findall(r'\*([A-Za-z_]\w*)', first)):
        if all(bare(L).search(b) for b in rest):
            branch = bare(L).sub('*' + L, branch, count=1)
    return branch


def proposer_alternatives():
    """{proposer: the other proposers with the same columns, names and types}, from the lib registry."""
    sig = {}
    for m in re.finditer(r'^\(proposer (\w+) .*?\(columns ((?:[^()]|\([^()]*\))*)\)\)', REGISTRY.read_text(), re.M):
        cols = tuple((c[0], c[1]) if isinstance(c, tuple) and c[1] else (c[2], BARE_COLUMN_TYPES.get(c[2]))
                     for c in re.findall(r'\((\w+) (\w+)\)|(\w+)', m[2]))
        sig[m[1]] = cols
    return {p: [q for q in sig if q != p and sig[q] == c] for p, c in sig.items()}


def parameter_of(text, pid):
    """The relation whose parameter form holds the edit pid, or None."""
    mask = code_mask(text)
    i = int(pid.split('.')[1])
    for a, b, head in top_forms(text, mask):
        if a <= i < b:
            m = re.match(r'\(\w+\s+(&\w+)', text[a:b])
            return m[1] if head in PARAMETER_FORMS and m else None
    return None


def edited_relation(text, pid):
    """The relation or instance of the top-level form that holds the edit pid."""
    mask = code_mask(text)
    i = int(pid.split('@')[0].split('.')[1])
    for a, b, head in top_forms(text, mask):
        if a <= i < b:
            m = re.match(r'\(\w+\s+(&\w+)', text[a:b])
            return m[1] if m else None
    return None


def judged(r, good, t, exs, edited, qf):
    """Whether table t of the edited program r is judged: t is a table of the edited form, and every table that t reads has the solver's rows
    at every example of exs, so that the edited query stands on correct inputs. The tables t reads are those of the relations and instances
    that its form reads (r's graph), and, for an output of an instance, the instance's input ports. A table that changes outside the edited
    form, such as a task parameter that is determined with the edited one, is not judged."""
    node, _, port = t.partition('.')
    if node != edited:
        return False
    names = set(r['digests'][exs[0]]) | set(good['digests'][exs[0]])
    reads = set(r['graph'].get(node, ()))
    ins = A.Q.component_inputs().get(qf.get(node, {}).get('component'), ())
    read = {u for u in names if u.split('.')[0] in reads}
    if port and port not in ins:
        read |= {u for u in names if u.partition('.')[0] == node and u.partition('.')[2] in ins}
    return all(r['digests'][e].get(u) == good['digests'][e].get(u) for e in exs for u in read)


def edits(text):
    """(edit id, description, edited text) of each single edit."""
    mask = code_mask(text)
    line = lambda i: text.count('\n', 0, i) + 1
    alternatives = proposer_alternatives()
    out = []
    for a, b, head in top_forms(text, mask):
        if head == 'OUT':
            continue
        if head in PARAMETER_FORMS:
            for m in re.finditer(r'(?<![\w&.:*^])([A-Z]\w+)(?![\w.])', text[a:b]):
                i, op = a + m.start(1), m.group(1)
                if mask[i] and op in alternatives:
                    for q in alternatives[op]:
                        out.append(('prop.%d.%s' % (i, q), 'line %d: %s for %s' % (line(i), q, op), text[:i] + q + text[i + len(op):]))
        for m in re.finditer(r'\((NOT|OR|!=|<=|>=|=|<|>|inside|interior) ', text[a:b]):
            i, op = a + m.start(), m.group(1)
            if not mask[i]:
                continue
            j = close_of(text, mask, i)
            if op == 'NOT':
                inner = text[i + 5:j].strip()
                out.append(('not.%d' % i, 'line %d: drop the negation of %s' % (line(i), inner[:60]), text[:i] + inner + text[j + 1:]))
            elif op == 'OR':
                kids = children(text, mask, i)
                if len(kids) > 1:
                    for k, (c, d) in list(enumerate(kids))[1:]:
                        out.append(('or.%d.%d' % (i, k), 'line %d: drop branch %d of an OR' % (line(i), k + 1), text[:c] + text[d:]))
                    (c0, d0), (c1, d1) = kids[0], kids[1]
                    second = exporting(text[c0:d0], [text[c:d] for c, d in kids[1:]], text[c1:d1])
                    out.append(('orx.%d.0' % i, 'line %d: drop branch 1 of an OR' % line(i), text[:c0] + text[d0:c1] + second + text[d1:]))
            elif op in TRADE:
                out.append(('trade.%d' % i, 'line %d: %s for %s' % (line(i), TRADE[op], op), text[:i + 1] + TRADE[op] + text[i + 1 + len(op):]))
            else:
                if op == '=' and text[i + 3:i + 4] == '*':
                    continue  # this = makes a label
                for name, table in (('turn', TURN), ('strict', STRICT)):
                    if op in table:
                        out.append(('%s.%d' % (name, i), 'line %d: (%s ...) for (%s ...)' % (line(i), table[op], op), text[:i + 1] + table[op] + text[i + 1 + len(op):]))
        for m in re.finditer(r'\.(minimal|maximal|rank|dual_rank)\b', text[a:b]):
            i, op = a + m.start(1), m.group(1)
            if mask[i]:
                out.append(('trade.%d' % i, 'line %d: .%s for .%s' % (line(i), TRADE[op], op), text[:i] + TRADE[op] + text[i + len(op):]))
    return out


def new_pairs(task, path, eng, n, select='valid'):
    """[(source example, input, output)]: up to n input variants, each with the solver's output on it, spread over the train pairs. select
    'valid' takes the variants that meet the preconditions of every table on the way to the output, in the file's order; 'any' takes input
    variants in a random order seeded by the task, whatever tables they change, so that each table's own preconditions can be checked later."""
    import random
    import outvariants as O
    import tablecache as C
    keep = ('id', 'kind', 'source', 'grid')
    base = next(l for l in J.records(path) if l['kind'] == 'base')
    if select == 'any':
        ins = [{k: v[k] for k in keep} for v in J.records(path) if v['kind'] == 'in']
        random.Random(task).shuffle(ins)
        want = {v['id']: v for v in ins[:8 * n]}
    else:
        post = A.postconditions(base)
        qf = A.Q.query_features(paths.read_gen(A.GEN / (task + '.arclog')))
        valid_in = A.valid_input(post, A.live_tables(base, qf))
        want = {v['id']: {k: v[k] for k in keep} for v in J.records(path) if valid_in(v)}
    per = -(-n // len(eng.bj['train']))
    got, seen = defaultdict(list), set()
    with C.Cache(task, eng, set(), hold=False) as cache:
        for rec, T, tj, ex in cache.hits(want):
            g = O.out_grid(T, ex, base['out'])
            key = json.dumps(rec['grid'])
            if g is None or key in seen or len(got[rec['source']]) >= per:
                continue
            seen.add(key)
            got[rec['source']].append((rec['source'], rec['grid'], g))
    out = [p for s in sorted(got) for p in got[s]]
    return out[:n]


def run(task, out_dir, variants_dir, n_pairs=24, select='valid'):
    import engine as E
    import features as F
    import proposers as PR
    import refeature as RF
    import run as R
    import tablecache as C
    import outvariants as O
    path = Path(out_dir) / (task + '.breaks.jsonl')
    done = {r['id'] for r in J.records(path)}
    started = Path(out_dir) / (task + '.started')  # each program's id, written before it runs
    begun = set(started.read_text().split()) if started.exists() else set()
    eng = C.Engine(task)
    pairs = None
    if 'pairs' in done:
        pairs = next(r for r in J.records(path) if r['id'] == 'pairs')['pairs']
    else:
        pairs = new_pairs(task, Path(variants_dir) / (task + '.variants.jsonl'), eng, n_pairs, select) if n_pairs else []
    tj = copy.deepcopy(eng.bj)
    n0 = len(tj['train'])
    tj['train'] = tj['train'] + [{'input': gi, 'output': go} for _, gi, go in pairs]
    exs = ['train/%d' % i for i in range(len(tj['train']))] + ['test/%d' % j for j in range(len(tj['test']))]
    programs = [('correct', 'the solver', eng.s.text)] + edits(eng.s.text)
    todo = [p for p in programs if p[0] not in done and not any(d.startswith(p[0] + '@') for d in done)]
    print('%s: %d new pairs, %d edits, %d programs to run' % (task, len(pairs), len(programs) - 1, len(todo)), flush=True)
    fcache = F.FeatureCache()
    t0 = time.time()
    with J.Appender(path) as fo, open(started, 'a') as fs:
        if 'pairs' not in done:
            fo.write(dict(id='pairs', n_train=n0, examples=exs, pairs=pairs, select=select))
        for n, (pid, desc, text) in enumerate(todo, 1):
            if pid in begun:  # an earlier run of this program was stopped, by a cap on memory or time, before its record was written
                fo.write(dict(id=pid, edit=desc, error='Stopped: an earlier run of this program passed the memory or time cap'))
                continue
            fs.write(pid + '\n')
            fs.flush()
            free = None if pid == 'correct' else parameter_of(eng.s.text, pid)
            try:
                s = eng.s if pid == 'correct' else E.Solver(task, text=text)
                if free is None:
                    runs = [(pid, s.tables(tj, pin=eng.pins, no_assignment=lambda p: PR.missing(p, eng.proposer_of, tj)), {})]
                else:
                    each, count = s.tables_each(tj, {r: v for r, v in eng.pins.items() if r != free}, MAX_ASSIGNMENTS)
                    if not each:
                        raise RuntimeError('no assignment')
                    runs = [('%s@%d' % (pid, k), T, dict(free=free, assignment=[list(r) for rel, rows, _ in key if rel == free for r in rows],
                                                         assignments=count)) for k, (key, T) in enumerate(each)]
                graph = E.reads(s.text)
                rd = E.table_reads(s.text)
                up = lambda g, name: E.upstream(g, name)
            except Exception as e:  # noqa: BLE001
                runs = []
                fo.write(dict(id=pid, edit=desc, error='%s: %s' % (type(e).__name__, str(e)[:300])))
            for rid, T, extra in runs:
                rec = dict(id=rid, edit=desc, **extra)
                try:
                    rec.update(missing=s.missing, graph={k: sorted(v) for k, v in graph.items()},
                               outputs={ex: O.out_grid(T, ex, [list(x) for x in s.out]) for ex in exs},
                               digests={ex: RF.digests(T, ex) for ex in exs},
                               features={ex: R.enc(F.all_features(T, ex, tj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance)) for ex in exs})
                except Exception as e:  # noqa: BLE001
                    rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
                fo.write(rec)
            el = time.time() - t0
            print('%s %d/%d %s %s  %.1fs each  eta %.0fs' % (task, n, len(todo), pid, '%d assignments' % len(runs) if free else 'ok' if runs else 'error',
                                                           el / n, (len(todo) - n) * el / n), flush=True)

def family(k):
    import growth
    return growth.family(k.split('|', 1)[1])


def score_task(task, out_dir):
    """Counters for one task, or None where it has no record of new pairs."""
    recs = list(J.records(Path(out_dir) / (task + '.breaks.jsonl')))
    head = next((r for r in recs if r['id'] == 'pairs'), None)
    good = next((r for r in recs if r['id'] == 'correct' and 'error' not in r), None)
    if head is None or good is None:
        return None
    n0, exs = head['n_train'], head['examples']
    own_ex = [e for e in exs if not (e.startswith('train/') and int(e.split('/')[1]) >= n0)]
    new_ex = [e for e in exs if e not in own_ex]
    c, fam = Counter(), defaultdict(Counter)
    import engine as E
    text = E.Solver(task).text
    qf = A.Q.query_features(text)

    def post_of(r):
        return A.postconditions({'examples': {e: r['features'][e] for e in own_ex}})

    def flagged(r, post, t):
        """The families of the postconditions of table t that fail at some new pair where the tables upstream of t keep theirs."""
        ups = A.upstream({k: set(v) for k, v in r['graph'].items()}, t)
        own = [k for k in post if k.split('|')[0] == t]
        pre = [k for k in post if k.split('|')[0].split('.')[0] in ups and not A.is_output(k)]
        out = set()
        for e in new_ex:
            f = r['features'][e]
            if all(A.holds(post[k], f.get(k, 'MISSING')) for k in pre):
                out |= {family(k) for k in own if not A.holds(post[k], f.get(k, 'MISSING'))}
        return out

    gpost = post_of(good)
    tables = {k.split('|')[0] for k in gpost}
    for t in tables:
        fs = flagged(good, gpost, t)
        c['correct tables'] += 1
        c['correct tables flagged'] += bool(fs)
        for f in fs:
            fam[f]['correct'] += 1
    for r in recs:
        if r['id'] in ('pairs', 'correct'):
            continue
        c['edits'] += 1
        if 'error' in r:
            c['illegal edits' if READER.search(r['error']) else 'edits that do not run'] += 1
            continue
        if all(r['outputs'][e] == good['outputs'][e] for e in exs):
            c['equivalent edits'] += 1
            continue
        c['broken programs'] += 1
        c['broken programs, wrong on the train pairs'] += any(r['outputs'][e] != good['outputs'][e] for e in own_ex if e.startswith('train/'))
        post = post_of(r)
        edited = edited_relation(text, r['id'])
        for t in {k.split('|')[0] for k in post}:
            if all(r['digests'][e].get(t) == good['digests'][e].get(t) for e in exs):
                continue
            if not judged(r, good, t, exs, edited, qf):
                c['changed tables not judged'] += 1
                continue
            c['broken tables'] += 1
            mine = {k: v for k, v in post.items() if k.split('|')[0] == t}
            theirs = {k: v for k, v in gpost.items() if k.split('|')[0] == t}
            shown = mine != theirs
            fs = flagged(r, post, t)
            c['broken tables shown on the train pairs'] += shown
            c['broken tables flagged on a new pair'] += bool(fs)
            c['broken tables shown or flagged'] += shown or bool(fs)
            for f in fs:
                fam[f]['broken'] += 1
    return c, fam


def score(out_dir, tasks):
    total, fam = Counter(), defaultdict(Counter)
    for task in tasks:
        got = score_task(task, out_dir)
        if got is None:
            print('%s: no records' % task, flush=True)
            continue
        c, f = got
        total.update(c)
        for k, v in f.items():
            fam[k].update(v)
        print('%s: %s' % (task, ', '.join('%s %d' % kv for kv in sorted(c.items()))), flush=True)
    print()
    for k in ('edits', 'illegal edits', 'edits that do not run', 'equivalent edits', 'broken programs', 'broken programs, wrong on the train pairs',
              'changed tables not judged', 'broken tables',
              'broken tables shown on the train pairs', 'broken tables flagged on a new pair', 'broken tables shown or flagged', 'correct tables',
              'correct tables flagged'):
        print('%-44s %6d' % (k, total[k]))
    print()
    print('%-44s %8s %8s' % ('family that flags', 'broken', 'correct'))
    for k, v in sorted(fam.items(), key=lambda kv: -kv[1]['broken']):
        print('%-44s %8d %8d' % (k[:44], v['broken'], v['correct']))


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(sys.argv[2], sys.argv[3], sys.argv[4], *(int(a) if a.isdigit() else a for a in sys.argv[5:]))
    else:
        score(sys.argv[2], sys.argv[3:])
