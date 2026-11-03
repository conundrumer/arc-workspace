"""Prints the numbers that partial.md quotes."""
import json
import os
H = os.path.dirname(os.path.abspath(__file__)) + '/'
R = {}
for l in open(H + 'reads.jsonl'):
    r = json.loads(l)
    R[r['section']] = r['value']
P = ('any', 'RULE', 'DET', 'INIT', 'any nonempty', 'RULE nonempty')
Q = ('any', 'RULE', 'DET', 'INIT', 'any reads', 'RULE reads', 'any no reads', 'RULE no reads', 'any no-read forms at pi', 'RULE no-read forms at pi')


def pf(x):
    for g in P:
        q = x[g]
        print('   per-form %-15s forms %7.1f now %.3f cond %.3f %s saving %+.3f %s over marginal %+.3f %s' % (g, q['forms'], q['bits_now'], q['bits_cond'], q['bits_cond_range'], q['saving'], q['saving_range'], q.get('saving_over_marginal', 0), q.get('saving_over_marginal_range')))


def po(x):
    for g in Q:
        q = x[g]
        print('   pooled %-26s rows %5d actual %.3f pi %.3f cond %.3f %s vs actual %+.3f %s vs pi %+.3f %s' % (g, q['rows'], q['kind_actual'], q['kind_under_pi'], q['kind_cond'], q['kind_cond_range'], q['saving_vs_actual'], q['saving_vs_actual_range'], q['saving_vs_pi'], q['saving_vs_pi_range']))


print('NONHELD picks6 together')
pf(R['nonheld_loto']['together'])
for k in ('closure', 'prefix', 'picks6-foreign'):
    print('NONHELD', k)
    pf(R['nonheld_rules'][k])
print('NONHELD hgb')
pf(R['secondary_nonheld'])
print('NONHELD control mean', R['nonheld_control']['mean'], R['nonheld_control']['low'], R['nonheld_control']['high'])
print('NONHELD plug in', json.dumps(R['nonheld_loto']['plug_in']))
print('HELD stand-in together')
pf(R['held_read']['together']['per_form'])
po(R['held_read']['together']['pooled'])
print('HELD stand-in marginal')
po(R['held_read']['marginal']['pooled'])
print('HELD hgb')
pf(R['secondary_held']['per_form'])
po(R['secondary_held']['pooled'])
print('HELD control first')
pf(R['held_control']['first']['per_form'])
po(R['held_control']['first']['pooled'])
print('HELD control means', R['held_control']['mean'], R['held_control']['pooled_mean'], min(R['held_control']['per_form_saving_over_marginal_each']), max(R['held_control']['per_form_saving_over_marginal_each']))
print('CEILING held LOTO')
c = R['held_loto_ceiling']
pf(c['together']['per_form'])
po(c['together']['pooled'])
print('ceiling control', c['control_mean'], min(c['control_saving_over_marginal_each']), max(c['control_saving_over_marginal_each']))
print('FACT ALONE: nonheld any, RULE, any nonempty, RULE nonempty; held any, RULE, any nonempty, RULE nonempty; ceiling any, RULE')
for f in ('last', 'kinds', 'leaves', 'head', 'cols', 'key', 'ident', 'stage', 'size'):
    n = R['nonheld_loto']['alone ' + f]
    h = R['held_read']['alone ' + f]['per_form']
    e = c['alone ' + f]['per_form']
    print('  %-7s' % f, ' '.join('%+.3f' % n[g]['saving_over_marginal'] for g in ('any', 'RULE', 'any nonempty', 'RULE nonempty')), '|', ' '.join('%+.3f' % h[g]['saving_over_marginal'] for g in ('any', 'RULE', 'any nonempty', 'RULE nonempty')), '|', ' '.join('%+.3f' % e[g]['saving_over_marginal'] for g in ('any', 'RULE')))
