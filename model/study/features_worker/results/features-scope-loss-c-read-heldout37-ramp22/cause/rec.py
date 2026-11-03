"""Records only: per measured form, the relation-pick gap S - R (read and builtin atoms), the scope size, the count of gold's ancestors (R's scope),
and the scope forms whose text equals one of gold's ancestors up to names. Writes cause/rec.tsv and prints correlations."""
import json
import math
import re
import statistics
import sys

KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools']
import search_node_score_parity as P  # noqa: E402

NAME = re.compile(r'&[rf]\d+')
norm = lambda t: re.sub(r'[*^](?=[A-Za-z_])', '', re.sub(r'&[rf]\d+(\.\w+)?', '&', t))  # noqa: E731
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
places = {}
for l in open(REC + '/places.tsv').read().split('\n')[1:]:
    if l:
        a, t, g, pl, s, r, gap = l.split('\t')
        places[(a, t, int(g), pl)] = (float(s) if s else None, float(r) if r else None, float(gap) if gap else None)
rows = [json.loads(l) for f in ('forms.0of2.jsonl', 'forms.1of2.jsonl') for l in open('%s/%s' % (REC, f))]
banks = {}
out = []
for r in rows:
    if r['status'] != 'mapped' or not r.get('S') or not r['S']['valid'] or not r['R']['valid']:
        continue
    a, t, g = r['arm'], r['task'], r['g']
    lines = [l for l in pe[t].strip().split('\n') if not l.startswith('(OUT')]
    heads = [l.split()[1] for l in lines]
    reads = [set(NAME.findall(l)) - {heads[i]} for i, l in enumerate(lines)]
    anc, todo = set(), [g]
    while todo:
        j = todo.pop()
        for h in reads[j]:
            if h in heads and heads.index(h) not in anc:
                anc.add(heads.index(h))
                todo.append(heads.index(h))
    direct = {heads.index(h) for h in reads[g] if h in heads}
    key = (a, t)
    if key not in banks:
        banks.clear()
        banks[key] = P.load_bank('%s/out/%s/%s/work/%s.out.jsonl.bank' % (RUN, a, t, t))
    fs = banks[key]['forms']
    anc_norm = {norm(lines[j]) for j in anc}
    same = [f for f in r['scope_fids'] if norm(fs[f].text) in anc_norm]
    kinds = {}
    for f in r['scope_fids']:
        kinds[fs[f].kind] = kinds.get(fs[f].kind, 0) + 1
    rr = places[(a, t, g, 'relation pick: read')]
    rb = places[(a, t, g, 'relation pick: builtin')]
    op = places[(a, t, g, 'op pick')]
    n_init_anc = sum(lines[j].startswith('(INIT') for j in anc)
    n_init_s = sum(fs[f].text.startswith('(INIT') for f in r['scope_fids'])
    out.append(dict(arm=a, task=t, g=g, kind=r['kind'], scope_n=r['scope_n'], anc_n=len(anc), direct_n=len(direct), same_text=len(same), extra=r['scope_n'] - len(same),
                    init_anc=n_init_anc, init_s=n_init_s, max_depth_s=max(fs[f].depth for f in r['scope_fids']),
                    S_read=rr[0], R_read=rr[1], gap_read=rr[2], S_bi=rb[0], R_bi=rb[1], gap_bi=rb[2], gap_op=op[2], S=r['S']['total'], R=r['R']['total'],
                    n_atoms=len(r['S']['atoms']), n_read_atoms=sum(1 for c, txt, b in r['S']['atoms'] if re.search(r'\((?:NOT \()?&[rf]', txt))))
cols = list(out[0])
with open(REC + '/cause/rec.tsv', 'w') as fh:
    fh.write('\t'.join(cols) + '\n')
    for x in out:
        fh.write('\t'.join(str(x[c]) for c in cols) + '\n')


def corr(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else float('nan')


print('forms', len(out))
for c in ('scope_n', 'anc_n', 'same_text', 'extra', 'init_s', 'max_depth_s', 'n_atoms', 'n_read_atoms'):
    print('%-12s median %5.1f  r(gap_read) %+.2f  r(gap_bi) %+.2f  r(gap_rel) %+.2f' % (c, statistics.median(x[c] for x in out), corr([x[c] for x in out], [x['gap_read'] for x in out]),
          corr([x[c] for x in out], [x['gap_bi'] for x in out]), corr([x[c] for x in out], [x['gap_read'] + x['gap_bi'] for x in out])))
lr = [math.log2(x['scope_n'] / max(x['anc_n'], 1)) for x in out]
print('log2(scope_n/anc_n) median %.2f r(gap_rel) %+.2f' % (statistics.median(lr), corr(lr, [x['gap_read'] + x['gap_bi'] for x in out])))
print('gap_read median %.2f, gap_bi median %.2f, R_read median %.2f, S_read median %.2f, R_bi median %.2f, S_bi median %.2f' % tuple(
    statistics.median(x[c] for x in out) for c in ('gap_read', 'gap_bi', 'R_read', 'S_read', 'R_bi', 'S_bi')))
for x in sorted(out, key=lambda x: -(x['gap_read'] + x['gap_bi'])):
    print(x['arm'][-2:], x['task'], 'g%-3d' % x['g'], x['kind'], 'scope', x['scope_n'], 'anc', x['anc_n'], 'same', x['same_text'], 'initS', x['init_s'], 'initA', x['init_anc'],
          'read %.2f->%.2f' % (x['R_read'], x['S_read']), 'bi %.2f->%.2f' % (x['R_bi'], x['S_bi']), 'op %+.2f' % x['gap_op'])
