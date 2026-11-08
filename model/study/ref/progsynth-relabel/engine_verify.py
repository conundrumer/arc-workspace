"""Verify judges' recovery clauses with the arclog engine.

usage: STUDY_RUN=<ast/run> <runtime python> -I engine_verify.py <render dir> <labels dir> <out.jsonl> [--only prefix ...] [--verbose]

Each judge clause is inserted into the mutant program right after the changed clause and the
program runs through the engine; the new relation's rows on each train input, at each kept DET
assignment, are compared with gold's rows from the pair's tables.json, up to a column permutation.
A read of an INIT's changed body is inlined; a changed DET makes the clause a DET with a reader.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[2]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, glob, gzip, itertools, json, os, sys, time, traceback
RUN = os.environ.get('STUDY_RUN', str(CODE_ROOT / 'ast/run')); sys.path.insert(0, RUN); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arclog
from filters import native, rows_at
from verify_recovery import parse, BOXES

FRESH = 'Zz'


def split_forms(text):
    out = []; depth = 0; start = None
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0: start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0: out.append(text[start:i + 1])
    return out


def unparse(t):
    return '(' + ' '.join(unparse(x) for x in t) + ')' if isinstance(t, list) else t


def is_site(x):
    return isinstance(x, list) and len(x) >= 2 and isinstance(x[0], str) and x[0].startswith(':')


def rename_labels(node, fn):
    """Apply fn(label) to every label at a site of the tree, nested sites included."""
    if isinstance(node, str): return node
    if is_site(node):
        return [node[0]] + [rename_labels(a, fn) if is_site(a) else fn(a) for a in node[1:]]
    if node and isinstance(node[0], str) and node[0] in ('=', '!=', '<', '<=', '>', '>='):
        return [node[0]] + [fn(a) for a in node[1:]]
    return [rename_labels(x, fn) for x in node]


def labels_of(node, out=None):
    out = set() if out is None else out
    if isinstance(node, str): return out
    if is_site(node):
        for a in node[1:]:
            if is_site(a): labels_of(a, out)
            elif a != '0': out.add(a.lstrip('*^'))
        return out
    if node and isinstance(node[0], str) and node[0] in ('=', '!=', '<', '<=', '>', '>='):
        for a in node[1:]:
            if a != '0': out.add(a.lstrip('*^'))
        return out
    for x in node: labels_of(x, out)
    return out


def made_labels(node, out=None):
    out = [] if out is None else out
    if isinstance(node, str): return out
    if is_site(node):
        for a in node[1:]:
            if is_site(a): made_labels(a, out)
            elif a.startswith('*') or a.startswith('^'):
                if a[1:] not in out: out.append(a[1:])
        return out
    for x in node: made_labels(x, out)
    return out


def inline_init(fix, changed, x_columns):
    """Replace each read of the changed INIT by the atoms of its key and of the input whose labels are X's columns."""
    name = changed[1]
    # with a key, the inputs nest inside the key form: (INIT &r Inst (key (atoms) (input ...) ...))
    if changed[3][0] == 'key': key_atoms, inputs = changed[3][1], changed[3][2:]
    else: key_atoms, inputs = [], changed[3:]
    body = None
    key_exports = {l for l in labels_of(key_atoms) if any(('^' + l) in json.dumps(key_atoms) for _ in [0])}
    for inp in inputs:
        if key_exports | labels_of(inp[2:]) == set(x_columns): body = key_atoms + inp[2:]; break
    if body is None:
        if key_exports == set(x_columns): body = list(key_atoms)
        else: raise ValueError('no INIT input has the labels of X: ' + ' '.join(x_columns))
    def replace(atoms):
        out = []
        for a in atoms:
            if isinstance(a, list) and a and a[0] == name:
                site_terms = {s[0][1:]: s[1] for s in a[1:] if is_site(s) and isinstance(s[1], str)}
                def fn(label):
                    if label == '0': return label
                    mark = label[0] if label[0] in '*^' else ''
                    base = label.lstrip('*^')
                    if base in site_terms:
                        term = site_terms[base]
                        if term.startswith('*'): return ('*' if mark else '') + term[1:]
                        return term  # the judge makes it elsewhere: join
                    return ('*' if mark else '') + base + FRESH
                out += [rename_labels(x, fn) for x in body]
            elif isinstance(a, list) and a and a[0] == 'OR':
                out.append(['OR'] + [replace(br) for br in a[1:]])
            elif isinstance(a, list) and a and a[0] == 'NOT':
                out.append(['NOT'] + replace(a[1:]))
            else:
                out.append(a)
        return out
    return [fix[0], fix[1]] + replace(fix[2:])


def canonical_or(node):
    """In a later branch of an OR, a label the first branch makes is named bare."""
    if not isinstance(node, list): return node
    if node and node[0] == 'OR':
        branches = [canonical_or(b) for b in node[1:]]
        first = set(made_labels(branches[0])) if branches else set()
        def strip(label):
            return label[1:] if label[:1] in '*^' and label[1:] in first else label
        return ['OR', branches[0]] + [rename_labels(b, strip) for b in branches[1:]]
    return [canonical_or(x) for x in node]


def build_program(rec, clause, x_columns, reader=True):
    forms = split_forms(rec['mutant_sexp']); k = int(rec['point'][0])
    changed = parse(forms[k]); fix = parse(clause)
    if not (isinstance(fix, list) and len(fix) >= 3 and fix[0] == 'RULE'): raise ValueError('not a RULE clause')
    fix[1] = '&fix'
    extra = []
    if changed[0] == 'INIT':
        fix = inline_init(fix, changed, x_columns)
    fix = canonical_or(fix)
    if changed[0] == 'DET':
        fix[0] = 'DET'
        if reader: extra = [['DET', '&fixread', [['&fix'] + [[':' + l, '*' + l] for l in made_labels(fix[2:])]][0]]]
    inserted = [unparse(fix)] + [unparse(e) for e in extra]
    return '\n'.join(forms[:k + 1] + inserted + forms[k + 1:]), k + 1, changed[0], changed[1]


def cell(c):
    return tuple(c)


def norm_rows(rows):
    return frozenset(tuple(cell(c) for c in r) for r in rows)


def flat(row):
    out = []
    for c in row:
        if isinstance(c, (list, tuple)): out += [int(x) for x in c]
        else: out.append(int(c))
    return tuple(out)


def decode_kept(kept, det_relations, det_types, skip=()):
    """{relation: sorted decoded rows} for the kept slots the table depends on; slot N is relation &rN.
    The changed relation's own slot is skipped: the mutant derives its own value."""
    types = {rel: list(ty) for rel, ty in zip(det_relations, det_types)}
    out = {}
    for item in kept:
        rel = '&r' + item['relation'].split()[-1]
        if rel not in types or rel in skip: continue
        # a kept slot may list fewer columns than the relation has here: the gold program's readers named fewer
        ncols = len(item['rows'][0]) if item['rows'] else len(types[rel])
        tys = types[rel][:ncols]
        try:
            rows = arclog.StudyProgram.decode_rows_json(tys, item['rows'])
        except Exception as exc:
            raise ValueError(f'decode {rel} types {tys} rows {str(item["rows"])[:80]}: {exc}')
        if isinstance(rows, str): rows = json.loads(rows)
        def cell_of(c):
            if 'margins' in c: m = c['margins']; return [m['top'], m['bottom'], m['left'], m['right']]
            return [c['value'] if 'value' in c else c['encoding_u32']]
        width = sum(4 if ty in BOXES else 1 for ty in tys)
        out[rel] = (tuple(sorted(flat([cell_of(c) for c in r]) for r in rows)), width)
    return out


def compatible(entry_assignment, want):
    """The entry's DET assignment agrees with the kept one on every slot the kept one fixes."""
    have = {rel: rows for rel, rows in entry_assignment}
    for rel, (rows, width) in want.items():
        if rel not in have: return False
        if tuple(sorted(flat(r)[:width] for r in have[rel])) != rows: return False
    return True


def ident_canonical(rows, types):
    """Rows with each Ident replaced by the sorted other-column rows sharing it: equal up to a renaming of ids."""
    idents = [i for i, t in enumerate(types) if t == 'Ident']
    if not idents: return frozenset(rows)
    rest = [i for i in range(len(types)) if i not in idents]
    out = []
    for r in rows:
        cells = list(r)
        for i in idents:
            members = tuple(sorted(tuple(x[j] for j in rest) for x in rows if x[i] == r[i]))
            cells[i] = ('ident', members)
        out.append(tuple(cells))
    return frozenset(out)


def compare(fix_rows_by_ex, fix_cols, gold_cols, gold_rows_by_ex):
    """fix rows match gold rows on every train input under one column choice (by name, else by type)."""
    names = [c['name'] for c in gold_cols]; types = [c['type'] for c in gold_cols]
    fnames = [c for c, _ in fix_cols]; ftypes = [t for _, t in fix_cols]
    gold_rows_by_ex = {ex: ident_canonical(rows, types) for ex, rows in gold_rows_by_ex.items()}
    def kind(t): return 'box' if t in BOXES else t
    choices = []
    if all(n in fnames for n in names):
        choices.append([fnames.index(n) for n in names])
    cands = [[i for i, t in enumerate(ftypes) if kind(t) == kind(ty)] for ty in types]
    for ch in itertools.product(*cands):
        if len(set(ch)) == len(ch) and list(ch) not in choices: choices.append(list(ch))
    for ch in choices:
        ok = True
        for ex, grows in gold_rows_by_ex.items():
            frows = fix_rows_by_ex.get(ex)
            if frows is None: ok = False; break
            proj = ident_canonical([tuple(r[i] for i in ch) for r in frows], types)
            if proj != grows: ok = False; break
        if ok: return True, [fnames[i] for i in ch]
    return False, None


def verify_pair(ev, settings, rec, clause, T, verbose=False, reader=True):
    x_columns = [c['name'] for c in T['assignments'][0]['mutant']['columns']]
    prog, kform, ckind, changed_name = build_program(rec, clause, x_columns, reader)
    try:
        gold = arclog.StudyProgram.from_sexp(prog, settings)
    except Exception as exc:
        return dict(engine='refused', reason=f'{type(exc).__name__}: {str(exc)[:300]}', program_kind=ckind, inserted=prog.split('\n')[kform])
    status, tables = ev.gold_tables(gold)
    st = json.loads(status) if isinstance(status, str) else status
    if st.get('status') != 'complete':
        if ckind == 'DET' and reader:
            return verify_pair(ev, settings, rec, clause, T, verbose, reader=False)
        return dict(engine='incomplete', reason=json.dumps(st)[:300], program_kind=ckind, inserted=prog.split('\n')[kform])
    n = native(tables); ts = n['tables']
    tf = [t for t in range(len(ts['form'])) if str(ts['form'][t]) == str(kform)]
    if not tf: return dict(engine='no table', reason='no table for the inserted form', program_kind=ckind)
    t = tf[0]
    schema, entries, _ = rows_at(n, t)
    fix_cols = list(zip(ts['column_names'][t], ts['column_types'][t]))
    kept = [decode_kept(k, ts['det_relations'][t], ts['det_types'][t], skip=(changed_name,)) for k in rec['evaluation']['kept_assignments']]
    if verbose:
        print('   inserted:', prog.split('\n')[kform][:400], file=sys.stderr)
        print('   fix columns', fix_cols, 'kept', str(kept)[:300], file=sys.stderr)
        for e in entries[:8]: print('   entry', e['example'], 'assignment', str(e['assignment'])[:160], 'rows', len(e['rows']), file=sys.stderr)
    out = dict(engine='ran', program_kind=ckind, fix_columns=[c for c, _ in fix_cols], assignments=[], inserted=prog.split('\n')[kform], reader=reader)
    all_ok = True
    for a, A in enumerate(T['assignments']):
        gold_cols = A['gold']['columns']
        if ckind == 'DET':
            grows = {0: norm_rows(A['gold']['train'][0][0])} if A['gold']['train'][0] else {0: frozenset()}
            frows = {}
            for e in entries:
                if e['example'][0] == 0 and compatible(e['assignment'], kept[a]): frows[0] = set(frows.get(0, set())) | set(e['rows'])
        else:
            grows = {ex: norm_rows(m[0]) if m else frozenset() for ex, m in enumerate(A['gold']['train'])}
            frows = {}
            for e in entries:
                if e['example'][0] != 1 or not compatible(e['assignment'], kept[a]): continue
                ex = e['example'][1]
                if ex in frows and frows[ex] != set(e['rows']):
                    frows[ex] = None  # several compatible entries disagree
                elif ex not in frows: frows[ex] = set(e['rows'])
        if any(v is None for v in frows.values()):
            out['assignments'].append(dict(assignment=a, ok=False, reason='compatible entries disagree')); all_ok = False
            if verbose: print('   assignment', a, 'compatible entries disagree', file=sys.stderr)
            continue
        ok, choice = compare({k: frozenset(v) for k, v in frows.items()}, fix_cols, gold_cols, grows)
        out['assignments'].append(dict(assignment=a, ok=ok, columns=choice, fix_counts={k: len(v) for k, v in sorted(frows.items())}, gold_counts={k: len(v) for k, v in sorted(grows.items())}))
        all_ok = all_ok and ok
        if verbose:
            print('   assignment', a, 'fix', {k: len(v) for k, v in sorted(frows.items())}, 'gold', {k: len(v) for k, v in sorted(grows.items())}, 'ok', ok, choice, file=sys.stderr)
            if not ok and frows:
                ex0 = min(frows); print('   sample fix', list(frows[ex0])[:2], 'gold', list(grows.get(ex0, []))[:2], file=sys.stderr)
    out['verified'] = all_ok
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('render'); ap.add_argument('labels'); ap.add_argument('out')
    ap.add_argument('--only', nargs='*', default=None); ap.add_argument('--verbose', action='store_true'); ap.add_argument('--deadline', type=float, default=None)
    a = ap.parse_args()
    cfg = json.load(open(DATA_ROOT / 'ast/run/corpus-v11/run.json'))
    settings = arclog.DecodeSettings(table_work_cap=cfg['work_cap'] * (64 if a.deadline else 1), rule_tests=False)
    pairs = []
    for mp in sorted(glob.glob(os.path.join(a.render, '*', 'meta.json'))):
        meta = json.load(open(mp)); pid = meta['pair_id']
        if a.only and not any(pid.startswith(p) for p in a.only): continue
        lp = os.path.join(a.labels, pid + '.json')
        if not os.path.exists(lp): continue
        pairs.append((meta, json.load(open(lp)), os.path.dirname(mp)))
    by_task = {}
    for meta, lab, d in pairs: by_task.setdefault(meta['task'], []).append((meta, lab, d))
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)['pair_id'] for l in open(a.out)}
    fout = open(a.out, 'a')
    for task, items in by_task.items():
        items = [it for it in items if it[0]['pair_id'] not in done]
        if not items: continue
        want = {(it[0]['case'], json.dumps(it[0]['edits'], sort_keys=True)): it for it in items}
        recs = {}
        for fn in ('recoverable.jsonl.gz', 'pairs.jsonl.gz'):
            if len(recs) == len(want): break
            p = os.path.join(DATA_ROOT, 'ast/run/corpus-v11', task, fn)
            if not os.path.exists(p): continue
            for l in gzip.open(p, 'rt'):
                d = json.loads(l); key = (d['case'], json.dumps(d['identity']['edits'], sort_keys=True))
                if key in want and key not in recs: recs[key] = d
                if len(recs) == len(want): break
        ev = arclog.StudyTaskEvaluator(task, cfg['tasks'], settings, session_bytes=cfg['session_mib'] * 1024 * 1024, compact=True)
        for key, (meta, lab, d) in want.items():
            t0 = time.time()
            row = dict(pair_id=meta['pair_id'], task=task, stratum=meta.get('stratum'), kind=meta['kind'], recovery=lab.get('recovery'))
            try:
                rec = recs[key]
                T = json.load(open(os.path.join(d, 'tables.json')))
                if not lab.get('recovery'): row.update(engine='skipped', reason='no recovery given')
                else: row.update(verify_pair(ev, settings, rec, lab['recovery'], T, a.verbose))
            except Exception as exc:
                row.update(engine='error', reason=f'{type(exc).__name__}: {str(exc)[:300]} @ {traceback.extract_tb(exc.__traceback__)[-1].lineno}')
            row['seconds'] = round(time.time() - t0, 2)
            fout.write(json.dumps(row) + '\n'); fout.flush()
            print(meta['pair_id'][:8], task, meta['kind'], row.get('engine'), row.get('verified'), row.get('reason', ''), f"{row['seconds']}s", file=sys.stderr)
        try: ev.finish_case()
        except Exception: pass


if __name__ == '__main__':
    main()
