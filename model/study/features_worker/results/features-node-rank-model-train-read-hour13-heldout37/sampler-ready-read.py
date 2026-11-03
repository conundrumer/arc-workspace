"""Tables for points 1 to 3 from the sampler- row files.

  python -I sampler-ready-read.py SET
"""
import os, sys
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
SET = sys.argv[1]
PFX = HERE + SET + '-'
F = pd.read_csv(PFX + 'sampler-form-rows.tsv', sep='\t')
Rd = pd.read_csv(PFX + 'sampler-read-rows.tsv', sep='\t')
Ph = pd.read_csv(PFX + 'sampler-phase-rows.tsv', sep='\t')
Op = pd.read_csv(PFX + 'sampler-opening-rows.tsv', sep='\t')
pd.set_option('display.width', 220, 'display.max_columns', 60, 'display.max_rows', 200)
F['nd'] = F['kind'] != 'DET'
F['held_share'] = F['held_openings'] / F['openings']
F['tries_share'] = F['held_tries'] / F['tries']
print('form-runs', len(F), 'by pop and kind')
print(F.groupby(['pop', 'kind']).size().unstack(fill_value=0))
print(F.groupby(['arm', 'pop']).size().unstack(fill_value=0))
print()


def held_tab(G, name):
    return dict(group=name, form_runs=len(G), openings=int(G['openings'].sum()), held=int(G['held_openings'].sum()), pooled=G['held_openings'].sum() / max(G['openings'].sum(), 1), median=G['held_share'].median(), zero=(G['held_openings'] == 0).mean(),
                tries_pooled=G['held_tries'].sum() / max(G['tries'].sum(), 1), right_kind_of_tries=G['right_kind_tries'].sum() / max(G['tries'].sum(), 1), via_anc=G['held_via_ancestor'].sum() / max(G['held_openings'].sum(), 1))


rows = []
for pop in ('ready_end', 'then_covered'):
    G = F[F['pop'] == pop]
    rows.append(held_tab(G, pop + ' all'))
    for k in ('RULE', 'INIT', 'DET'):
        rows.append(held_tab(G[G['kind'] == k], pop + ' ' + k))
    for nr, sel in (('1 read', G['nreads'] == 1), ('2 reads', G['nreads'] == 2), ('3+ reads', G['nreads'] >= 3)):
        rows.append(held_tab(G[sel], pop + ' ' + nr))
print(pd.DataFrame(rows).round(4).to_string(index=False))
print()
# calibration of the race model on sampled openings
F['pred'] = F['p_actual'] * F['model_n']
print('calibration: sampled openings', int(F['model_n'].sum()), 'held actual', int(F['model_held'].sum()), 'held predicted', round(F['pred'].sum(), 1))
for pop in ('ready_end', 'then_covered'):
    G = F[F['pop'] == pop]
    print(' ', pop, 'actual', int(G['model_held'].sum()), 'predicted', round(G['pred'].sum(), 1))
print()
# point 3: counterfactuals, one step
for pop in ('ready_end', 'then_covered'):
    G = F[F['pop'] == pop]
    w = G['model_n']
    print(pop, 'mean over form-runs, weight by sampled openings; then median over form-runs')
    t = {}
    for c in ('p_actual', 'p_top1', 'p_top100', 'p_group10', 'p_distinct', 'p_flat'):
        t[c] = [float((G[c] * w).sum() / w.sum()), float(G[c].median()), float((G[c] >= .1).mean()), float((G[c] >= .5).mean())]
    print(pd.DataFrame(t, index=['weighted mean', 'median', 'share >= .1', 'share >= .5']).round(5).to_string())
    print()
# phases, by read kind
Ph['s_share'] = Ph['rank_score'] / Ph['n']
Ph['x_share'] = Ph['rank_weight'] / Ph['n']
Ph['t_share'] = Ph['rank_table_score'] / Ph['tables']
Ph = Ph.merge(F[['arm', 'task', 'h', 'pop', 'kind', 'nreads']], on=['arm', 'task', 'h'])
Ph = Ph.merge(Rd[['arm', 'task', 'h', 'q', 'qkind', 'qdepth']], on=['arm', 'task', 'h', 'q'])
for pop in ('ready_end', 'then_covered'):
    for ph in ('start', 'mid', 'end'):
        G = Ph[(Ph['pop'] == pop) & (Ph['phase'] == ph)]
        print(pop, ph, 'pairs', len(G), 'median: n %d, rank by score %d (share %.3f), rank by weight %d (share %.3f), table rank share %.3f, score %.2f, best uses %.0f, gap to the bar %.2f nats, own share %.3g, reach share %.3g, p_read %.3g' % (
            G['n'].median(), G['rank_score'].median(), G['s_share'].median(), G['rank_weight'].median(), G['x_share'].median(), G['t_share'].median(), G['best_score'].median(), G['best_uses'].median(), G['bar_gap'].median(), G['own_share'].median(), G['reach_share'].median(), G['p_read'].median()))
        for qk in ('RULE', 'INIT', 'DET'):
            H = G[G['qkind'] == qk]
            if len(H):
                print('   read kind %s pairs %d: rank by score share %.3f [%.3f, %.3f], by weight %.3f, score %.2f, uses %.0f, gap %.2f, p_read %.3g' % (qk, len(H), H['s_share'].median(), H['s_share'].quantile(.25), H['s_share'].quantile(.75), H['x_share'].median(), H['best_score'].median(), H['best_uses'].median(), H['bar_gap'].median(), H['p_read'].median()))
print()
# the group over time
Op['bin'] = pd.cut(Op['sec'], [0, 60, 300, 600, 1200, 2400, 3700])
print(Op.groupby('bin', observed=True)[['n', 'tables', 'wmax_x', 'bar_nats', 'neff', 'n50', 'top10', 'top100', 'top1000', 'median_x', 'mean_x']].median().round(3).to_string())
print()
print(F[F['pop'] == 'ready_end'].sort_values(['task', 'arm', 'h'])[['arm', 'task', 'h', 'kind', 'nreads', 'depth', 'sec_ready', 'sec_end', 'openings', 'held_openings', 'held_via_ancestor', 'any_read_held', 'held_tries', 'tries', 'right_kind_tries', 'p_actual', 'p_top1', 'p_top100', 'p_group10', 'p_distinct', 'p_flat']].to_string(index=False))
