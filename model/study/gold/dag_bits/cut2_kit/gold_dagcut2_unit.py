"""Small checks of gold_dagcut2_one.py. Run in this folder, through gold_dagcut2_env.sh.

  gold_dagcut2_unit.py pure                      commits and the stop, on made-up chains and on chains of outcut99 rows
  gold_dagcut2_unit.py retry STEM LINE...        reads the lines of the stem (lines.json), as `read` does, and shows the retry with the field order of the tokens
  gold_dagcut2_unit.py port STEM                 canon_lines against or_q.canonical_lines, screen against or_q.walk_order
  gold_dagcut2_unit.py read STEM                 the state of the start text, read whole, against the pod-all row of the stem
  gold_dagcut2_unit.py bar STEM ROWS.jsonl [LINES.json]   S.decoded by hand on `working` and on `program` of the last row, apart from the loop
"""
import glob, json, os, sys
import gold_dagcut2_one as T

POD = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits/pod-all/'


def chain(worsts, undrawn=None, margin=3, tentative=3):
    """(indexes of the committed steps, steps run) for the worst forms [start, step 0, step 1, ...]; undrawn: the same for the count of forms with no bits."""
    undrawn = undrawn or [0] * len(worsts)
    c = T.Chain((undrawn[0], worsts[0], 0), margin, tentative)
    got = []
    for k in range(1, len(worsts)):
        if c.land((undrawn[k], worsts[k], 0)):
            got.append(k - 1)
        if c.stop():
            return got, k
    return got, len(worsts) - 1


def expect(name, got, want):
    print('  ', 'ok  ' if got == want else 'FAIL', name, got)
    if got != want:
        sys.exit(1)


def pure():
    print('commits and the stop')
    expect('fewer forms with no bits commits with no fall', chain([30, 31, 31], [2, 1, 1]), ([0], 2))
    expect('as many forms with no bits and a fall of 2.99 does not', chain([30, 27.01], [1, 1]), ([], 1))
    expect('a fall of 3 does', chain([30, 27.0], [1, 1]), ([0], 1))
    expect('a rise in forms with no bits does not', chain([30, 10], [0, 1]), ([], 1))
    expect('stop after 3 tentative steps', chain([30, 29, 28, 27.5, 10]), ([], 3))
    expect('a commit resets the count', chain([30, 29, 20, 19, 18, 10]), ([1, 4], 5))
    expect('steps add up from the last commit', chain([30, 28.5, 26.9]), ([1], 2))
    expect('the next fall counts from the new commit', chain([30, 28.5, 26.9, 20]), ([1, 2], 3))
    expect('margin 0 commits every step that gains', chain([30, 29.9, 29.8, 29.7, 29.6], margin=0), ([0, 1, 2, 3], 4))
    # outcut99 worst forms (before, then each step)
    expect('21897d95 commits steps 0, 3, 4, 6', chain([80.888, 70.88, 70.003, 69.828, 49.122, 41.485, 40.953, 33.597, 33.56]), ([0, 3, 4, 6], 8))
    expect('c4d067a0 commits nothing and stops at 3 of 5 steps', chain([43.923, 43.738, 41.611, 41.477, 41.209, 41.185]), ([], 3))
    expect('7c66cb00 commits steps 2 and 4', chain([32.303, 31.715, 30.94, 25.928, 23.08, 22.542, 22.399]), ([2, 4], 6))
    expect('target_of: the least text among forms with no bits', T.target_of({0: 5.0, 1: None, 2: None}, ['(RULE &a)', '(RULE &z)', '(RULE &b)']), 2)
    expect('target_of: ties of the worst form go to the least text', T.target_of({0: 5.0, 1: 5.0, 2: 3.0}, ['(RULE &z)', '(RULE &b)', '(RULE &a)']), 1)
    print('pure ok')


def lines_of(stem):
    return [x for x in json.load(open('lines.json'))[stem] if x.strip()]


def retry(stem, which):
    T.load_sampler()
    T.setup(stem, 'lines.json', 600)
    W = T.body_of(T.S.base_lines)
    canon = T.canon_lines(W, T.SESS)[0]
    import or_q
    for i in which:
        scope = or_q.canonical_scope(canon, i)
        f0 = T.P.read(T.P.sampler, stem, W, i, canon, 60)
        b, s = T.read(W, canon, i)
        print('line', i, W[i].split()[0], '| plain walk:', f0['status'], f0['bits'], 'bad', [x[:60] for x in f0.get('bad') or []][:2], '| read:', b, s, 'retry', T.RETRY.get(W[i]))
    print('counts', {k: v for k, v in T.counts.items() if 'retr' in k or k == 'dag reads'})


def port(stem):
    import time, or_q, live, live_try
    T.load_sampler()
    T.setup(stem, 'lines.json', 600)
    body = T.body_of(T.S.base_lines)
    sess = T.SESS
    want = or_q.canonical_lines(body, sess)
    got = T.canon_lines(body, sess)
    again = T.canon_lines(body, sess)
    print(stem, 'canon_lines equals or_q.canonical_lines:', got == want, again == want, 'forms', len(body))
    canon = want[0]
    ok = n = 0
    for i in range(0, len(body), max(1, len(body) // 6)):
        kind = body[i].split()[0].lstrip('(')
        if kind not in live.KIND_TOK:
            continue
        scope = or_q.canonical_scope(canon, i)
        s2, j2, _ = live_try.session_of(stem)
        w = or_q.walk_order(T.P.sampler, stem, kind, [len(scope), 0], scope, canon[i], s2, j2, kind)
        v = sum(w['parts'].values()) if or_q.clean(w) else None
        a = T.screen(stem, scope, canon[i], kind, None)
        b = T.screen(stem, scope, canon[i], kind, 1.0)
        good = (a is None and v is None) or (a is not None and v is not None and abs(a - v) < 0.011)
        print('  line', i, kind, 'walk_order', None if v is None else round(v, 2), 'screen', a, 'limit 1:', 'OVER' if b is T.F.OVER else b, 'ok' if good else 'DIFF')
        ok += good
        n += 1
    print('screen agrees on', ok, 'of', n)
    if got != want or again != want or ok != n:
        sys.exit(1)


def pod_row(stem):
    for p in sorted(glob.glob(POD + 'rows-*.jsonl')):
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            if r.get('task') == stem:
                return r


def read(stem):
    T.load_sampler()
    T.setup(stem, 'lines.json', 600)
    W = T.body_of(T.S.base_lines) + [x for x in T.S.base_lines if x.startswith('(OUT')]
    st, bits, status = T.dag_state(W)
    row = pod_row(stem)
    bad = 0
    for f in row['forms']:
        b = bits.get(f['line'])
        same = (f['bits'] is None and b in (None, 'none')) or (isinstance(b, (int, float)) and f['bits'] is not None and abs(b - f['bits']) <= 0.01)
        if not same:
            bad += 1
            print('  DIFF line', f['line'], 'pod', f['bits'], f['status'], 'now', b, status.get(f['line']))
    print(stem, 'state', st, 'pod worst', row['worst'], 'sum', row['sum'], '| forms differing from the pod row:', bad, 'of', len(row['forms']), '| retried', T.counts['fields retried'], T.counts['fields retried with bits'])
    if bad:
        sys.exit(1)


def bar(stem, path, lines='lines.json'):
    T.load_sampler()
    T.setup(stem, lines, 600)
    rows = [json.loads(l) for l in open(path) if l.startswith('{"task"')]
    r = rows[-1]
    W0 = T.body_of(T.S.base_lines) + [x for x in T.S.base_lines if x.startswith('(OUT')]
    ended, att = T.S.direct('\n'.join(W0))
    T.GOLD = dict(attempts=att, rows=T.S.walk(W0))
    print('start text ends', ended, 'steps', len(r['steps']), 'committed', [k for k, s in enumerate(r['steps']) if s['committed']], 'program_fail', r.get('program_fail'))
    for name in ('working', 'program'):
        ls = r[name].split('\n')
        nf, why = T.S.legal(ls)
        print(name, 'legal:', None if nf is None else 'normal form of %d lines, equal to the text: %s' % (len(nf), nf == ls), why)
        if nf is not None:
            print('  decoded:', T.S.decoded(ls, nf, T.GOLD), 'rows_flags', T.rows_flags(T.S.decoded(ls, nf, T.GOLD)[0]))


if __name__ == '__main__':
    what = sys.argv[1]
    if what == 'pure':
        pure()
    elif what == 'retry':
        retry(sys.argv[2], [int(x) for x in sys.argv[3:]])
    elif what == 'port':
        port(sys.argv[2])
    elif what == 'read':
        read(sys.argv[2])
    else:
        bar(*sys.argv[2:5])
