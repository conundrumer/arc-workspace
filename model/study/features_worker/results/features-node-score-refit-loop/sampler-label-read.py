"""The label matrix, the chance curve and where picks land.

  python -I sampler-label-read.py
"""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import aucs as A
TASKS = '2c0b0aff 74dd1130 aa18de87 b9b7f026 d23f8c26 5b37cb25 8e2edd66 b2862040 4df5b0ae 94133066 c35c1b4c d0f5fe59 e69241bd'.split()
pd.set_option('display.width', 240, 'display.max_columns', 60, 'display.max_rows', 300)
L = pd.read_csv(HERE + 'sampler-label-auc-rows.tsv', sep='\t')
idx = A.boot_idx(13)
out = []
for (cut, lab, m), G in L.groupby(['cut', 'label', 'measure']):
    v = G.groupby('task')['auc'].mean().reindex(TASKS).values
    p, lo, hi = A.band(v, idx)
    out.append(dict(cut=cut, label=lab, measure=m, auc=p, lo=lo, hi=hi, positives=int(G['positives'].sum()), tasks=int(np.isfinite(v).sum()), median_beat=G['median_beat'].median()))
O = pd.DataFrame(out)
order = ['open_nondet', 'ready_nondet', 'open_not_ready', 'open_read', 'ready_any', 'ready_q_rule', 'any_read', 'closed_read']
meas = ['table_score', 'table_x', 'node_score_all_copies', 'node_score_best_copy', 'node_x_best_copy', 'table_score_S1']
for cut in (600, 3600):
    print('cut', cut)
    T = O[O['cut'] == cut]
    rows = []
    for lab in order:
        r = dict(label=lab)
        for m in meas:
            x = T[(T['label'] == lab) & (T['measure'] == m)]
            if len(x):
                x = x.iloc[0]
                r[m] = '%.3f [%.3f,%.3f]' % (x['auc'], x['lo'], x['hi'])
                r['pos' if m == 'table_score' else 'p_' + m] = x['positives']
        rows.append(r)
    print(pd.DataFrame(rows)[['label', 'pos', 'table_score', 'table_x', 'node_score_all_copies', 'node_score_best_copy', 'node_x_best_copy', 'table_score_S1']].to_string(index=False))
    print()
Cv = pd.read_csv(HERE + 'sampler-chance-curve-rows.tsv', sep='\t')
cols = [c for c in Cv.columns if c.startswith(('p_', 'mass'))] + ['n', 'xmax', 'bar', 'median_x']
print(Cv.groupby('cut')[cols].median().T.to_string())
print()
Rk = pd.read_csv(HERE + 'sampler-pick-rank-rows.tsv', sep='\t')
P = Rk.groupby(['time_bin', 'key'])['count'].sum().unstack(0)
print(P.to_string())
s = P.loc[['1-10', '11-100', '101-1000', '1001+', 'top_share_.01', 'top_share_.71']] / P.loc['all']
print((s).round(4).to_string())
print('mean rank share of the least-used pick', (P.loc['rest_rank_share_sum'] / P.loc['rest']).round(3).to_dict(), 'mean id', (P.loc['rest_id_sum'] / P.loc['rest']).round(0).to_dict())
print()
Pos = pd.read_csv(HERE + 'sampler-positive-rows.tsv', sep='\t')
Pos['p_own'] = pd.to_numeric(Pos['p_own'])
Pos['p_reach'] = pd.to_numeric(Pos['p_reach'])
Pos['tshare'] = Pos['rank_table_score'] / Pos['tables']
Pos['nshare'] = Pos['rank_node_score'] / Pos['n']
Pos['xshare'] = Pos['rank_node_x'] / Pos['n']
for cut in (600, 3600):
    for lab in ('open_nondet', 'ready_nondet', 'ready_read'):
        G = Pos[(Pos['cut'] == cut) & (Pos[lab] == 1)]
        print(cut, lab, 'positives', len(G), 'median: table rank share %.3f, node rank share %.3f, weight rank share %.3f, score %.2f, x %.2f, gap to bar %.2f, copies %.0f, p_own %.3g, p_reach %.3g, uses_end %.0f' % (G['tshare'].median(), G['nshare'].median(), G['xshare'].median(), G['score'].median(), G['x'].median(), G['bar_gap'].median(), G['copies'].median(), G['p_own'].median(), G['p_reach'].median(), G['uses_end'].median() if cut == 3600 else -1))
        bins = pd.cut(G['tshare'], [0, .01, .1, .18, .3, .5, 1.0])
        print(G.groupby(bins, observed=True).agg(n=('p_own', 'size'), p_own=('p_own', 'median'), p_reach=('p_reach', 'median'), gap=('bar_gap', 'median'), score=('score', 'median'), kinddet=('kind', lambda s: (s == 'DET').mean()), depth=('depth', 'median')).round(5).to_string())
