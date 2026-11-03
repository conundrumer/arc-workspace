"""The census walk of frontier_q.py on the forms of the 37 held-out tasks, in 3 columns: round 50 text, the helper view and this revision. Each row of census-heldout.json is one JSON line for one form, column and scope. A restart skips rows of the same program text, and a walk of the same form, context and task is taken from an earlier row. Writes the counts to the views entry of manifest.json.

  <runtime python> gold_cover_census.py
A form is drawable when its walk has no error, a total, `bad` empty, no `dead` and no tokens left. Bits are `total` of drawable forms. Priors: SEARCH_MODELS. Steers as in a helper round, with no STEER_COVER.
"""
import hashlib, json, os, statistics, sys

sys.path.insert(0, os.environ['SAMPLER_CODE'])
import live, or_q
import search_gold as G
from frontier_q import parents

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
HELP = D + 'gold/gold-v3-helper-forms-a036da074/'
HELD = D + 'sampler/sampler-worker/held/tasks.txt'
OUT = 'census-heldout.json'
KEEP = 'column', 'task', 'line', 'scope', 'kind', 'nscope', 'target', 'total', 'bad', 'dead', 'left', 'error', 'program', 'context'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def columns(held):
    text = json.load(open('current-text.json'))
    helper = {p['task']: p['gold_sexp'] for p in json.load(open(HELP + 'points-eval.json'))}
    this = {p['task']: p['gold_sexp'] for p in json.load(open('points-eval.json'))}
    return dict(round50={t: '\n'.join(text[t]['lines']) for t in held}, helper={t: helper[t] for t in held}, this={t: this[t] for t in held})


def drawable(r):
    return not r.get('error') and r.get('total') is not None and not r.get('bad') and r.get('dead') is None and not r.get('left')


def summary(held, cols):
    rows = {}
    for l in open(OUT):
        r = json.loads(l)
        rows[r['column'], r['task'], r['line'], r['scope'], r['program']] = r
    got = dict(definition=__doc__.split('\n')[3], priors=os.path.basename(os.environ['SEARCH_MODELS']), stems=len(held), scopes=dict(parents='the forms the target reads, the context of the Forms drawable figure', before='every earlier form'))
    for name, prog in cols.items():
        got[name] = {}
        want = {t: sha(prog[t]) for t in held}
        for scope in ('parents', 'before'):
            rs = [r for k, r in rows.items() if k[0] == name and k[3] == scope and want[k[1]] == k[4]]
            ok = [r for r in rs if drawable(r)]
            by = {}
            for r in rs:
                by.setdefault(r['task'], []).append(drawable(r))
            got[name][scope] = dict(forms=len(rs), forms_drawable=len(ok), stems_all_drawable=sum(all(v) for v in by.values()), median_bits=round(statistics.median(r['total'] for r in ok), 2) if ok else None)
    return got


def main():
    held = open(HELD).read().split()
    cols = columns(held)
    seen, walks = set(), {}
    if os.path.exists(OUT):
        for l in open(OUT):
            r = json.loads(l)
            seen.add((r['column'], r['program'], r['task'], r['line'], r['scope']))
            walks[r['task'], r['context']] = r
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    with open(OUT, 'a') as f:
        for name, prog in cols.items():
            for t in held:
                psha = sha(prog[t])
                lines = [x for x in prog[t].splitlines() if x.strip()]
                for i, target in enumerate(lines):
                    kind = target.split()[0].lstrip('(')
                    if kind == 'OUT':
                        continue
                    for scope, keep in (('parents', parents(lines, i)), ('before', list(range(i)))):
                        if (name, psha, t, i, scope) in seen:
                            continue
                        ctx = [lines[j] for j in keep] + [target]
                        csha = sha('\n'.join(ctx))
                        q = walks.get((t, csha))
                        if q is None:
                            if kind not in live.KIND_TOK:
                                q = dict(error='the walk has no kind ' + kind)
                            else:
                                G.gold_of = lambda task, c, p, ls=ctx: (task, ls)
                                try:
                                    q = or_q.one(sampler, t, kind, [len(keep), 0], kind)
                                except Exception as e:  # noqa: BLE001
                                    q = dict(error=repr(e)[:200])
                        row = {k: q.get(k) for k in KEEP}
                        row.update(column=name, task=t, line=i, scope=scope, kind=kind, nscope=len(keep), target=target, program=psha, context=csha)
                        walks[t, csha] = row
                        f.write(json.dumps(row) + '\n')
                        f.flush()
            print(name, 'done', flush=True)
    got = summary(held, cols)
    m = json.load(open('manifest.json'))
    m['views']['corpus-view']['census_heldout'] = got
    with open('manifest.json.new', 'w') as f:
        json.dump(m, f, indent=1)
    os.replace('manifest.json.new', 'manifest.json')
    print(json.dumps(got, indent=1))


if __name__ == '__main__':
    main()
