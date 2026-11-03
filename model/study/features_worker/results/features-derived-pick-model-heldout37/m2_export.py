"""Writes X/m2-export.pkl: the fitted rank model (logit) and the calibrated gate of X/fit-cal as plain numbers (dicts, lists, floats, strings; no numpy, no sklearn).

    python3 m2_export.py
"""
import json
import pickle

X = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
FIT = X + '/fit-cal'
m = json.load(open(FIT + '/model.json'))
g = json.load(open(FIT + '/gate.json'))
assert m['rank'] == 'logit'
out = dict(
    version='m2-cal-1',
    note='Score of a derived option o: s_o = sum_i beta[i] * (x_i - mean[i]) / scale[i], x the raw fact vector of o over `logit_names` (a fact named in `logit_ignore` is skipped; a column type '
         'fact ct:T with T not in `coltypes` adds to ct:other). Gate: z = (sum_i coef[i] * (g_i - gmean[i]) / gscale[i] + intercept) * temp + bias, sigma = 1 / (1 + exp(-z)); the raw gate facts g '
         'are `gate_names`, where lse = LSE(s) - log(n_D) and mx = max(s) - LSE(s) over the scores s of the derived options with ws > 0. See m2-facts.md.',
    logit_names=m['names'], logit_mean=m['mean'], logit_scale=m['scale'], logit_beta=m['beta'], coltypes=m['coltypes'], logit_ignore=m.get('ignore', []), logit_lambda=m['lam'],
    gate_names=g['names'], gate_mean=g['mean'], gate_scale=g['scale'], gate_coef=g['coef'], gate_intercept=g['intercept'], gate_C=g['C'], temp=g['temp'], bias=g['bias'],
)
pickle.dump(out, open(X + '/m2-export.pkl', 'wb'), protocol=2)
print('wrote', X + '/m2-export.pkl', {k: (len(v) if isinstance(v, list) else v if not isinstance(v, str) or len(v) < 40 else '...') for k, v in out.items() if k != 'note'})
