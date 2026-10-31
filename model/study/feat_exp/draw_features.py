"""Compute every enabled feature module on a clause sampler's draws, and write a values table.

Usage: /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python draw_features.py DRAWS.jsonl.gz OUT.csv.gz
           [--names NAMES.json] [--rules FILE] [--soft KEYS] [--workers N] [--bound SECONDS] [--limit N]
           [--rules-first] [--stream-only]

DRAWS is a draws file in the format `rulecheck_draws.py` reads (RULE, DET and INIT port draws). The draws of a point
need an exported point directory in `fstore/points/`; a draw without one has status `no point dir`. Run it through
`scripts/run_heavy.py --cpus N`.

Every module of `features/enabled.txt` runs on each draw, through the same `rulecheck.RuleCheck` view as the rule keys:
the train inputs and outputs, the available tables, X, the candidate's clause, the clauses before the point and the library
interfaces. At a DET point X keeps every non-Example body column (as `rulecheck_draws.py` does without
`--read-later-clauses`); the stored gold values were computed on a table that keeps only the columns later clauses read, so a
DET feature that depends on the column set can differ between the two.

OUT has one row per draw, in the column names of `values.csv.gz` (`featlib.FEATURES` function names, a function that returns
a dict giving `<function>.<key>`; the `form.*` columns that a clause lacks are 0, as `features.columns` does). Before the
feature columns:

    pair_id        `task|case|point|draw`
    candidate      `draw`, or `gold` for the sampler's gold draw (draw 0 at each point)
    task, case, point, kind (Rule, Det, `INIT key`, `INIT input`), draw
    clause         the draw's clause text, relation names mapped to the program's where they are known
    status         `ok`, `no clause`, `no point dir` or `error: ...`; a row that is not `ok` has no feature values
    passes         status ok, the sampler did not fail the draw, no static match other than `valid`, and no hard key fires
                   (an empty X passes: gold's X can be empty)
    hard_keys      the keys of the rule file that fire, minus the soft keys, joined by `;`
    soft_score     a passing draw's score under `rulecheck.SoftScore` (the default model), from the values below
    soft_keep      whether the score is within the model's margin of the best score of the draw's point (in OUT only,
                   once every draw of the point is in; the stream has the scores)
    errors         the feature functions that raised, space-separated, and `bound` where the draw ran past its
                   bound; their columns are empty. '' where none did
    s_*            stratum fields (strata.py); `s_d_out` is a reporting column and no key's input
    seconds        wall seconds for the draw (building X and every module)

Each point's rows are appended to OUT.stream.jsonl.zst (framed zstd JSONL, `judge3.framed_jsonl`) as the point
finishes, one JSON row per draw, so a reader can use them before the run ends; a run started again with the same OUT
computes only the draws not in that file. A run whose plain OUT.stream.jsonl exists keeps appending to that file. A draw
that repeats an earlier draw of its point (same clause and X, both gold or both not) takes that draw's values, which are
computed once.
The timing table (seconds per module and per draw) is written next to OUT as OUT.timing.txt. OUT.formtest.json tells which
columns read X's rows: --form-test N computes N draws per slice of 40 again with every row of X removed, and a column whose value
never changes there reads no rows (gap.py takes it as `form-only`). A draw whose modules take
longer than --bound seconds keeps the values it has finished and leaves the rest empty; it has no soft_score, and its
passes is empty where the bound cut a rule function and no finished one fired.
"""
import argparse
import collections as C
import hashlib
import json
import multiprocessing as mp
import os
import re
import signal
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import featlib  # noqa: E402
import rulecheck  # noqa: E402
import strata  # noqa: E402
from featlib import FEATURES  # noqa: E402
from rulecheck import RuleCheck, names_from_gold, rename_relations  # noqa: E402
from rulecheck_draws import POINTS, point_dirs, read_draws  # noqa: E402
from judge3.framed_jsonl import JsonlWriter, iter_lines  # noqa: E402  (on the path that rulecheck_draws adds)

HERE = Path(__file__).resolve().parent
# Rule keys that a stricter key of the same rule file replaces; they count as soft (the sampler's SUPERSEDED).
SOFT_DEFAULT = ('final_vs_output.fewer_rows,final_vs_output.same_every_example,available_size.equals_input,'
                'contains_input.equal,contains_input.strict_superset,before_order.not_strict_order,'
                'q1_atom_laws.compose_ab_equal,q1_off_grid.frame_bad,q1_equal_cols.box_input_equal,'
                'q1_equal_cols.ident_equal,q4c_declared.differs_no_box')


PAIR_HEAD = re.compile(rb'^\{"pair_id":\s*("(?:[^"\\]|\\.)*")')
SLICE = 40  # draws of one point per job, so that a point with many draws spreads over the workers


def key_point(key):
    return json.loads(key[2])[0]


class Bound(BaseException):
    pass


def _alarm(signum, frame):
    raise Bound()


def enabled_modules():
    """The modules of `features/enabled.txt`, or the comma-separated modules of the environment variable DRAW_MODULES
    (for computing a few new modules into a separate stream; their rule keys only are checked)."""
    if os.environ.get('DRAW_MODULES'):
        return os.environ['DRAW_MODULES'].split(',')
    return (HERE / 'features/enabled.txt').read_text().split()


def flat(name, v):
    """The (column, value) pairs of a feature function's result, as `features.frame` names them."""
    if isinstance(v, dict):
        return [(f'{name}.{k}', x) for k, x in v.items()]
    return [(name, v)]


SOFT = None
SOFT_MARGIN = rulecheck.SoftScore.margin_of(rulecheck.DEFAULT_SOFT)


def slim_draw(line):
    """The fields of a draw that main reads, with the whole line compressed in `raw`; run_point parses `raw` again. The
    main process keeps every draw of a pass, so it keeps this form."""
    d = json.loads(line)
    s = {k: d.get(k) for k in ('task', 'case', 'point', 'draw', 'gold', 'clause')}
    s['xkey'] = hashlib.sha1(json.dumps(d.get('x'), sort_keys=True).encode()).hexdigest()
    s['raw'] = zlib.compress(line if isinstance(line, bytes) else line.encode(), 1)
    return s


def run_point(job):
    key, dname, draws, rules, names_in, soft, bound, form_n, rules_first = job
    draws = [dict(json.loads(zlib.decompress(d['raw'])), _i=d['_i']) if 'raw' in d else d for d in draws]
    global SOFT
    if SOFT is None and rulecheck.DEFAULT_SOFT.exists():
        SOFT = rulecheck.SoftScore()
    rulecheck.load_feature_modules(enabled_modules())
    rows, took, setup = [], C.defaultdict(float), 0.0
    form = C.defaultdict(lambda: [0, 0])  # column -> [draws where it has a value, of those where emptying X's rows changed it]
    t0 = time.perf_counter()
    try:
        rc = RuleCheck(POINTS / dname, rules)
        gold_text = (POINTS / dname / 'gold.arclog').read_text()
        forms = strata.sexprs(gold_text)
        lines = [l for l in gold_text.splitlines() if l.strip()]
        gold_line = lines[rc.point[0]]
        pf = strata.point_fields(forms, rc.point[0])
        golds = [d for d in draws if d.get('gold') and d.get('clause')]
        names = names_in or (names_from_gold(golds[0]['clause'], gold_line) if golds else {})
    except Exception as e:
        return [(d['_i'], dict(status=f'error: {type(e).__name__}: {str(e)[:80]}')) for d in draws], {}, 0, {}
    setup = time.perf_counter() - t0
    fams = set(enabled_modules())
    mine = {n: f for n, f in FEATURES.items() if f.family in fams}
    rule_fns = [n for n in mine if n in rc.functions]
    ordered = [(n, mine[n]) for n in rule_fns] + [(n, f) for n, f in mine.items() if n not in rc.functions]
    signal.signal(signal.SIGALRM, _alarm)
    for d in draws:
        res = {}
        began = time.perf_counter()
        if d.get('fail') or not d.get('clause') or not d.get('x') or not d.get('x_rows'):
            res['status'] = 'no clause'
            rows.append((d['_i'], res))
            continue
        try:
            clause = rename_relations(d['clause'], names)
            x = rc.draw_x(d, clause)
            reads = rc.gold_out_reads(clause)
            cand = rc.candidate(clause, x, out_reads=reads)
            res['kind'] = cand.kind
            res['clause'] = clause
            res['s'] = strata.as_columns(d.get('point_group') or d.get('stratum') or pf,
                                         strata.candidate_fields(forms, rc.point[0], clause))
            vals, bad, at = {}, [], len(ordered)
            cut = rules_first and bool(d.get('fail') or static_prune(d))
            signal.setitimer(signal.ITIMER_REAL, bound)
            try:
                for k, (name, fn) in enumerate(ordered):
                    at = k
                    if rules_first and k == len(rule_fns):
                        cut = cut or any(c in rc._rule_set and c not in soft and rulecheck._fires(v) for c, v in vals.items())
                        if cut:
                            break
                    b = time.perf_counter()
                    try:
                        v = fn(cand)
                    except Exception:
                        bad.append(name)
                        rc.errors[name] += 1
                        continue
                    finally:
                        took[fn.family] += time.perf_counter() - b
                    for col, val in flat(name, v):
                        vals[col] = val
                at = len(ordered)
            except Bound:
                rc.errors['bound'] += 1
                bad.append('bound')
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            res['errors'] = ' '.join(bad)
            if form_n > 0 and vals and not cut:
                form_n -= 1
                empty = dict(x, entries=[dict(e, rows=[]) for e in x['entries']])
                other = {}
                signal.setitimer(signal.ITIMER_REAL, bound)
                try:
                    c2 = rc.candidate(clause, empty, out_reads=reads)
                    for name, fn in FEATURES.items():
                        try:
                            v = fn(c2)
                        except Exception:
                            v = None
                        other.update(flat(name, v))
                except Bound:
                    other = None
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                if other is not None:
                    for col, val in vals.items():
                        if val is not None and val == val:
                            o = other.get(col)
                            form[col][0] += 1
                            form[col][1] += not (o == val or (o != o and val != val))
            fired = sorted(k for k, v in vals.items() if k in rc._rule_set and rulecheck._fires(v))
            hard = [k for k in fired if k not in soft]
            res['hard_keys'] = ';'.join(hard)
            res['passes'] = not (d.get('fail') or static_prune(d) or hard)
            if 'bound' in bad and at < len(rule_fns) and res['passes']:
                res['passes'] = None
            res['values'] = vals
            if SOFT and res['passes'] and 'bound' not in bad and not os.environ.get('DRAW_MODULES'):
                res['soft_score'] = SOFT.score_values(vals)
            res['status'] = 'ok'
        except Exception as e:
            res['status'] = f'error: {type(e).__name__}: {str(e)[:80]}'
        res['seconds'] = time.perf_counter() - began
        rows.append((d['_i'], res))
    took['_point_setup'] = setup
    took['_errors'] = sum(rc.errors.values())
    return rows, dict(took), len(draws), dict(form)


def static_prune(d):
    """Whether the sampler's static check proves the draw unsatisfiable or constant. A `valid` match (an atom that
    always holds) does not prune: gold clauses have them."""
    return any(m.get('class') != 'valid' for m in (d.get('static') or {}).get('matches') or [])


def pair_id(d):
    return f"{d['task']}|{d['case']}|{json.dumps(d['point'])}|{d['draw']}"


def row_of(d, r):
    """The output row of draw d from its result r."""
    row = dict(pair_id=pair_id(d), candidate='gold' if d.get('gold') else 'draw', task=d['task'], case=d['case'],
               point=json.dumps(d['point']), kind=r.get('kind'), draw=d['draw'], status=r['status'],
               clause=r.get('clause'), passes=r.get('passes'), hard_keys=r.get('hard_keys'), seconds=r.get('seconds'),
               errors=r.get('errors'), soft_score=r.get('soft_score'))
    row.update(r.get('s') or {})
    row.update(r.get('values') or {})
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('draws')
    ap.add_argument('out')
    ap.add_argument('--names')
    ap.add_argument('--rules', default=str(rulecheck.DEFAULT_RULES), help='rule keys: the keys whose firing makes a draw not pass')
    ap.add_argument('--soft', default=SOFT_DEFAULT, help='comma-separated rule keys that count as soft')
    ap.add_argument('--workers', type=int, default=int(os.environ.get('ARC_HEAVY_CPUS', 1)))
    ap.add_argument('--bound', type=float, default=60.0, help='seconds one draw\'s modules may take')
    ap.add_argument('--form-test', type=int, default=2, metavar='N',
                    help='per slice of up to 40 draws of a point, N ok draws are computed again with the rows of X emptied; the columns whose value never '
                    'changes read no rows (written to OUT.formtest.json as {column: [draws with a value, draws changed]}); 0 none')
    ap.add_argument('--limit', type=int, help='read only the first N draws')
    ap.add_argument('--stream-only', action='store_true',
                    help='read only the pair ids of the stream and skip the draws already in it without parsing them; '
                    'append this pass\'s draws to the stream, and write no OUT table (the timing table covers this pass)')
    ap.add_argument('--rules-first', action='store_true',
                    help='compute the functions of the rule set first, and the other functions only for a draw that passes')
    a = ap.parse_args()
    import pandas as pd
    t0 = time.time()
    try:
        names_all = json.loads(Path(a.names).read_text()) if a.names else {}
    except ValueError:
        print(f'{a.names} is not complete JSON (still being written?); names come from gold alignment', flush=True)
        names_all = {}
    stream_path = Path(a.out + '.stream.jsonl')
    if not stream_path.exists():
        stream_path = Path(a.out + '.stream.jsonl.zst')
    streamed, skip = {}, set()
    if stream_path.exists():
        for line in iter_lines(stream_path):
            if a.stream_only:
                m = PAIR_HEAD.match(line if isinstance(line, bytes) else line.encode())
                if m:
                    skip.add(json.loads(m[1]))
                    continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if a.stream_only:
                skip.add(row['pair_id'])
            else:
                streamed[row['pair_id']] = row
        print(f'resuming: {len(streamed) + len(skip)} draws already in {stream_path}', flush=True)
    draws = read_draws(a.draws, skip, slim_draw)[:a.limit]
    for i, d in enumerate(draws):
        d['_i'] = i
    if a.stream_only and not draws:
        print(f'no new draws; {time.time() - t0:.0f}s', flush=True)
        return
    dirs = point_dirs({d['task'] for d in draws})
    # A draw that repeats an earlier draw of its point (same clause and X, both gold or both not) takes that draw's
    # result; only the first of them is computed.
    by_point, first, copies, copied = C.OrderedDict(), {}, C.defaultdict(list), []
    for d in draws:
        k = (d['task'], d['case'], json.dumps(d['point']), bool(d.get('gold')), d.get('clause'),
             d['xkey'])
        if pair_id(d) in streamed:
            first.setdefault(k, d)
        elif k in first:
            f = first[k]
            if pair_id(f) in streamed:
                copied.append(dict(streamed[pair_id(f)], pair_id=pair_id(d), draw=d['draw']))
            else:
                copies[f['_i']].append(d)
        else:
            first[k] = d
            by_point.setdefault(k[:3], []).append(d)
    soft = set(filter(None, a.soft.split(',')))
    rules = rulecheck.read_rules(a.rules)
    jobs, results = [], {}
    for key, ds in by_point.items():
        if key in dirs:
            names = names_all.get('|'.join(key))
            golds = [d for d in ds if d.get('gold') and d.get('clause')]
            if not names and golds:
                lines = [l for l in (POINTS / dirs[key] / 'gold.arclog').read_text().splitlines() if l.strip()]
                names = names_from_gold(golds[0]['clause'], lines[key_point(key)])
            for i in range(0, len(ds), SLICE):
                part = ds[i:i + SLICE]
                jobs.append((key, dirs[key], part, rules, names or {}, soft, a.bound, a.form_test, a.rules_first))
        else:
            for d in ds:
                for c in [d] + copies[d['_i']]:
                    results[c['_i']] = dict(status='no point dir')
    stream = JsonlWriter(stream_path) if stream_path.suffix == '.zst' else stream_path.open('a')
    for row in copied:
        streamed[row['pair_id']] = row
        stream.write(row if isinstance(stream, JsonlWriter) else json.dumps(row) + '\n')
    stream.flush()
    todo = sum(len(ds) for ds in by_point.values())
    print(f'{len(draws)} draws, {todo} to compute ({len(draws) - len(streamed) - todo} repeat an earlier draw), '
          f'{len(by_point)} points, {len(jobs)} jobs, {time.time() - t0:.0f}s', flush=True)
    spent, ndraws, setup, errors = C.defaultdict(float), 0, 0.0, 0
    formtest = C.defaultdict(lambda: [0, 0])

    def take(part):
        nonlocal ndraws, setup, errors
        rows, took, n, form = part
        for col, (n_val, n_chg) in form.items():
            formtest[col][0] += n_val
            formtest[col][1] += n_chg
        for i, r in rows:
            for d in [draws[i]] + copies[i]:
                results[d['_i']] = r if not a.stream_only else {k: v for k, v in r.items() if k not in ('s', 'values')}
                row = row_of(d, r)
                stream.write(row if isinstance(stream, JsonlWriter) else json.dumps(row) + '\n')
        stream.flush()
        for k, v in took.items():
            if k == '_point_setup':
                setup += v
            elif k == '_errors':
                errors += v
            else:
                spent[k] += v
        ndraws += n if isinstance(n, int) else 0

    if a.workers > 1:
        with mp.get_context('spawn').Pool(a.workers) as pool:
            for n, part in enumerate(pool.imap_unordered(run_point, jobs), 1):
                take(part)
                if n % 10 == 0:
                    print(f'{n} of {len(jobs)} points, {time.time() - t0:.0f}s', flush=True)
    else:
        for j in jobs:
            take(run_point(j))
    stream.close()
    table, status = [], C.Counter()
    for d in draws:
        row = streamed.get(pair_id(d)) or row_of(d, results[d['_i']])
        if a.stream_only:
            row = {k: row.get(k) for k in ('status', 'passes', 'seconds', 'errors', 'soft_score', 'task', 'case', 'point')}
        status[row['status'].split(':')[0]] += 1
        table.append(row)
    df = pd.DataFrame(table)
    for c in df.columns:
        if c.startswith('form.'):
            df[c] = df[c].fillna(0).where(df['form.atoms'].notna())
        if c in FEATURES or c.split('.')[0] in FEATURES:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if 'soft_score' in df.columns:
        best = df.groupby(['task', 'case', 'point']).soft_score.transform('max')
        df['soft_keep'] = (df.soft_score >= best - SOFT_MARGIN).where(df.soft_score.notna())
    if not a.stream_only:
        df.to_csv(a.out, index=False)
    ok = max(status['ok'], 1)
    L = [f'{"module":<28}{"seconds":>10}{"share":>8}{"ms/draw":>10}']
    tot = sum(spent.values()) or 1.0
    for m, s in sorted(spent.items(), key=lambda kv: -kv[1]):
        L.append(f'{m:<28}{s:>10.1f}{s / tot:>8.1%}{1000 * s / ok:>10.1f}')
    wall = df['seconds'].dropna()
    L += ['', f'draws with status ok: {status["ok"]} of {len(draws)}; modules {tot:.1f} s in all, {1000 * tot / ok:.1f} ms per ok draw',
          f'whole draw (X build, strata, modules): mean {1000 * wall.mean():.1f} ms, median {1000 * wall.median():.1f} ms, '
          f'p90 {1000 * wall.quantile(.9):.1f} ms, max {1000 * wall.max():.0f} ms' if len(wall) else '',
          f'point setup (state, tables, prefix typing): {setup:.1f} s over {len(jobs)} points, {1000 * setup / max(len(jobs), 1):.0f} ms each',
          f'feature errors: {errors}; by function: '
          f'{dict(C.Counter(n for e in df["errors"].dropna() for n in str(e).split()).most_common()) or "none"}']
    Path(a.out + '.formtest.json').write_text(json.dumps(formtest))
    Path(a.out + '.timing.txt').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))
    print(f'status {dict(status)}; passes {int((df.passes == True).sum())}; wrote {a.out}; {time.time() - t0:.0f}s', flush=True)  # noqa: E712


if __name__ == '__main__':
    main()
