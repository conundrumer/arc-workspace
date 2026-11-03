"""Checks against the stall read's rows, the split of the gap to the bar, the same-size test, the chance as the group grows.

  python -I sampler-cross-checks.py
"""
import os, sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
ST = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-hour-stall-read-fold13/'
pd.set_option('display.width', 220, 'display.max_columns', 60, 'display.max_rows', 200)
F = pd.read_csv(HERE + 'sampler-form-rows.tsv', sep='\t')
Rd = pd.read_csv(HERE + 'sampler-read-rows.tsv', sep='\t')
Ph = pd.read_csv(HERE + 'sampler-phase-rows.tsv', sep='\t')
Ph = Ph.merge(F[['arm', 'task', 'h', 'pop', 'kind', 'nreads', 'sec_ready']], on=['arm', 'task', 'h']).merge(Rd[['arm', 'task', 'h', 'q', 'qkind']], on=['arm', 'task', 'h', 'q'])
Hold = pd.read_csv(ST + 'hold-rows.tsv', sep='\t')
Hold = Hold[Hold['arm'].isin(['hour_s0', 'hour_s1'])]
print('stall hold-rows, form-runs', Hold.groupby(['arm', 'task', 'form']).ngroups, 'visits', Hold['visits'].sum(), 'held visits', Hold['held_visits'].sum(), 'held tries', Hold['held_tries'].sum(), 'of tries', Hold['tries'].sum(), 'right tries', Hold['right_tries'].sum())
E = F[F['pop'] == 'ready_end']
print('this read, ready_end', len(E), 'visits', E['visits'].sum(), 'held visits', E['held_visits'].sum(), 'held tries', E['held_tries'].sum(), 'of tries', E['tries'].sum(), 'right kind tries', E['right_kind_tries'].sum())
H2 = Hold.groupby(['arm', 'task', 'form'], as_index=False)[['visits', 'tries', 'held_visits', 'held_tries', 'right_tries']].sum().rename(columns={'form': 'h'})
M = E.merge(H2, on=['arm', 'task', 'h'], how='outer', suffixes=('', '_stall'), indicator=True)
print(M['_merge'].value_counts().to_dict())
m = M[M['_merge'] == 'both']
print('form-runs with equal held visits', int((m['held_visits'] == m['held_visits_stall']).sum()), 'of', len(m), '; sum this', int(m['held_visits'].sum()), 'stall', int(m['held_visits_stall'].sum()))
print(m[m['held_visits'] != m['held_visits_stall']][['arm', 'task', 'h', 'nreads', 'visits', 'visits_stall', 'held_visits', 'held_visits_stall', 'held_tries', 'held_tries_stall']].to_string(index=False))
print()
print('held by time, stall rows (visits in the bin that fall after the form is ready)')
Hold['bin'] = pd.cut(Hold['lo'], [-1, 599, 1799, 3700], labels=['0-600', '600-1800', '1800-3600'])
print(Hold.groupby('bin', observed=True)[['visits', 'held_visits', 'tries', 'held_tries']].sum().assign(share=lambda d: d['held_visits'] / d['visits']).to_string())
print()
# stall's numbers
Rp = pd.read_csv(ST + 'read-pick-rows.tsv', sep='\t')
Rp = Rp[Rp['arm'].isin(['hour_s0', 'hour_s1'])].dropna(subset=['best_weight_rank'])
print('stall read-pick-rows, hour arms', len(Rp), 'rank quartiles', Rp['best_weight_rank'].quantile([.25, .5, .75]).tolist(), 'score quartiles', Rp['best_score'].quantile([.25, .5, .75]).tolist(), 'chance quartiles', Rp['chance_per_draw'].quantile([.25, .5, .75]).tolist())
print()
# the gap to the bar, split: from the read's weight to the top weight, from the top weight to the bar
Ph['rank_nats'] = Ph['wtop'] - Ph['best_x']
Ph['group_nats'] = Ph['bar_gap'] - Ph['rank_nats']
Ph['rank_abs'] = Ph['rank_weight']
Ph['ln_n'] = np.log(Ph['n'])
G = Ph[Ph['pop'] == 'ready_end']
print(G.groupby('phase')[['n', 'bar_gap', 'rank_nats', 'group_nats', 'ln_n', 'rank_abs', 'p_read']].median().round(4).to_string())
print('by read kind, phase end')
print(G[G['phase'] == 'end'].groupby('qkind')[['n', 'bar_gap', 'rank_nats', 'group_nats', 'rank_abs', 'p_read']].median().round(4).to_string())
print('share of the gap in rank nats, median over pairs with a positive gap', G[(G['bar_gap'] > 0)].groupby('phase').apply(lambda d: (d['rank_nats'] / d['bar_gap']).median(), include_groups=False).round(3).to_dict())
print()
# chance as the group grows: ready_end pairs with a window that starts early
for lab, sel in (('all pairs', G), ('non-DET reads', G[G['qkind'] != 'DET']), ('RULE reads', G[G['qkind'] == 'RULE'])):
    print(lab, 'median p_read by phase', sel.groupby('phase')['p_read'].median().to_dict(), 'median n', sel.groupby('phase')['n'].median().to_dict(), 'rank share', (sel['rank_score'] / sel['n']).groupby(sel['phase']).median().round(3).to_dict())
print()
# same size, other rank
S = Ph[Ph['phase'] == 'start'].copy()
S['share'] = S['rank_score'] / S['n']
for lo, hi in ((0, 200), (200, 1000), (1000, 100000)):
    s = S[(S['n'] > lo) & (S['n'] <= hi)]
    print('window starts with n in (%d, %d]' % (lo, hi))
    print(s.groupby('pop').agg(pairs=('n', 'size'), n=('n', 'median'), rank_abs=('rank_score', 'median'), share=('share', 'median'), score=('best_score', 'median'), gap=('bar_gap', 'median'), p_read=('p_read', 'median')).round(4).to_string())
F['ln_p'] = np.log(F['p_actual'].clip(lower=1e-7))
print()
print('form-runs: flat draw above the actual chance', int((E['p_flat'] > E['p_actual']).sum()), 'of', len(E))
print('rank 100 or better chance gain, medians of ratios: top1 %.0f, top100 %.1f, group10 %.1f, distinct %.2f, flat %.1f' % tuple((E[c] / E['p_actual'].clip(lower=1e-7)).median() for c in ('p_top1', 'p_top100', 'p_group10', 'p_distinct', 'p_flat')))
print('misses removed, weighted over sampled openings:', {c: round(float((((E[c] - E['p_actual']) / (1 - E['p_actual'])) * E['model_n']).sum() / E['model_n'].sum()), 4) for c in ('p_top1', 'p_top100', 'p_group10', 'p_distinct', 'p_flat')})
print()
print('ready_end one-read forms held share by nats', )
one = E[E['nreads'] == 1].merge(Rd[['arm', 'task', 'h', 'q', 'qkind', 'own_pick_openings', 'reach_pick_openings', 'rest_pick_openings', 'held_openings']], on=['arm', 'task', 'h'], suffixes=('', '_q'))
print(one[['openings', 'held_openings', 'own_pick_openings', 'reach_pick_openings', 'rest_pick_openings']].sum().to_dict())
two = E[E['nreads'] == 2]
print('two-read forms: any read held', int(two['any_read_held'].sum()), 'all held', int(two['held_openings'].sum()), 'of', int(two['openings'].sum()), '; p_top1', round(two['p_top1'].median(), 4))
print('uncovered at the last write, counts from the stall table: 224 form-runs; ready with reads', len(E), '; ready with no reads, not read here: 10')
