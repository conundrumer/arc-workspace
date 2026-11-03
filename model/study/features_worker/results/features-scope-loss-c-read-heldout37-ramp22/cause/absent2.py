"""For the forms whose read relation is absent from the recorded scope: each relation of the gold form q that the clause reads, by name, and the
scope relations whose table equals it (by merge key). Reuses ../job.py up to main."""
import json
import sys

REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
src = open(REC + '/job.py').read()
src = src[:src.rindex('\nmain()')]
sys.argv = ['job.py']
ns = dict(__name__='jobmod', __file__=REC + '/job.py')
exec(compile(src, REC + '/job.py', 'exec'), ns)
D = ns['D']
rows = [json.loads(l) for f in ('forms.0of2.jsonl', 'forms.1of2.jsonl') for l in open('%s/%s' % (REC, f))]
items = {(a, t, g): (a, t, g, s, f) for a, t, g, s, f in ns['build_items']()}
for r in rows:
    if r['status'] != 'read relation not in the scope':
        continue
    c = ns['ctx_of'](r['arm'], r['task'])
    v, fids, scope = ns['scope_of'](c, r['opening'])
    sess, d, _ = D.session_of(r['task'])
    grel, srel = ns['relations'](c.lines, sess, d), ns['relations'](scope, sess, d)
    q = c.heads.index(r['absent'][0].split('.')[0])
    # sub-names of q's INIT relations, from the gold lines' reads
    by_g = {val['slot']: k for k, val in grel.items()}
    gtext = {l.split()[1]: l for l in c.lines}
    subs = ns['learn_subs'](c.lines, gtext, by_g, sess)
    comp = c.lines[q].split()[2]
    print('=' * 90)
    print(r['arm'], r['task'], 'g%d' % r['g'], 'reads', r['absent'][0], 'q =', q, c.lines[q][:120])
    for k, val in grel.items():
        if val['form'] != q:
            continue
        name = k[0] if k[1] is None else '%s.%s' % (k[0], '/'.join(sorted(subs.get((comp, k[1]), {str(k[1])}))))
        eq = [(sk, scope[val2['form']][:90]) for sk, val2 in srel.items() if val2['key'] == val['key']]
        print('  gold relation %-22s labels %-30s scope relations with an equal table: %s' % (name, val['labels'], eq))
