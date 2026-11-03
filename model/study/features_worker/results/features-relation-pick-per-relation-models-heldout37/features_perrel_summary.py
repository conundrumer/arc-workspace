#!/usr/bin/env python
"""Joins the held reads into summary.json and summary.md: the bars, the ladder of key levels, the keys that pass, and the controls. Each number comes from a final-*.json of this record."""
import json
import os

ME = os.path.dirname(os.path.abspath(__file__)) + '/'
ARMS = ['hyb-noorder', 'hyb-all', 'rel', 'comp', 'fam']
out = {}
L = ['| Model | Keys with a model | Saved, all picks | Gold alive | Minus rank read, no content | Control, all picks | Control, gold alive |', '|---|---|---|---|---|---|---|']
f3 = lambda v: '%+.3f (%+.3f to %+.3f)' % tuple(v)  # noqa: E731
for a in ARMS:
    r, c = json.load(open(ME + 'read-final-%s.json' % a)), json.load(open(ME + 'read-control-%s.json' % a))
    L.append('| %s | %d | %s | %s | %s | %s | %s |' % (a, r['keys_with_model'], f3(r['saved']), f3(r['saved_alive']), f3(r['saved_minus_rank_structure']), f3(c['saved']), f3(c['saved_alive'])))
    big = [k for k in r['keys_table'] if k['t'] >= 8 or k['n'] >= 50]
    cbig = [k for k in c['keys_table'] if k['t'] >= 8 or k['n'] >= 50]
    out[a] = dict(saved=r['saved'], alive=r['saved_alive'], control=c['saved'], control_alive=c['saved_alive'], keys_big=len(big), pass_gold=r['keys_pass_gold'], pass_net=r['keys_pass_net'], share_gold=r['share_picks_pass_gold'], share_net=r['share_picks_pass_net'],
                  control_pass_gold=c['keys_pass_gold'], control_pass_net=c['keys_pass_net'], control_share_gold=c['share_picks_pass_gold'], control_share_net=c['share_picks_pass_net'],
                  sum_net_big_bits=r['sum_net_big'], control_sum_net_big_bits=c['sum_net_big'], sum_net_all_bits=r['sum_net_all'], control_sum_net_all_bits=c['sum_net_all'],
                  sum_gold_big_bits=r['sum_gold_saved_big'], control_sum_gold_big_bits=c['sum_gold_saved_big'],
                  score_ms_per_pick=r['score_ms_per_pick'], trees_used=r['trees_used'], held_gold_share_keys_no_model=r['held_gold_share_keys_no_model'])
L.append('')
L.append('| Model | Keys read | Pass at gold picks | Their share of picks | Control passes | Net pass | Their share | Control net passes | Sum of net bits, keys read | Control sum |')
L.append('|---|---|---|---|---|---|---|---|---|---|')
for a in ARMS:
    o = out[a]
    L.append('| %s | %d | %s | %.3f | %d | %s | %.3f | %d | %.0f | %.0f |' % (a, o['keys_big'], ', '.join(o['pass_gold']), o['share_gold'], len(o['control_pass_gold']), ', '.join(o['pass_net']), o['share_net'], len(o['control_pass_net']), o['sum_net_big_bits'], o['control_sum_net_big_bits']))
json.dump(out, open(ME + 'summary.json', 'w'), indent=1)
open(ME + 'summary.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
