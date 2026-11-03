"""One cost per form: mean bits over random valid orders less log2 of the count of valid orders, an upper bound on -log2 of the sum over orders. Reads form-bits.tsv, written by features_dag_census_read.py, and writes set-cost.tsv and prints a summary. With --join it reads form-bits-join.tsv and writes set-cost-join.tsv.

The count of a form is its count of DAG orders times the share of random walks the engine kept, since the mode check refuses orders the DAG allows. A form with no kept walk has no random mean and stays out of the rows, and the summary counts those forms.

  features_dag_set_cost.py [--join] [FOLDER]
"""
import collections, csv, math, os, statistics, sys
args = sys.argv[1:]
tail = '-join' if '--join' in args else ''
args = [a for a in args if a != '--join']
D = args[0] if args else os.path.dirname(os.path.abspath(__file__))
every = list(csv.DictReader(open(f'{D}/form-bits{tail}.tsv'), delimiter='\t'))
rows = [r for r in every if r['random_mean'] and r['n_orders'] and r['written']]
none = collections.Counter(r['scope'] for r in every if r['written'] and r['n_orders'] and not r['random_mean'] and int(r['random_refused'] or 0))
out = []
for r in rows:
    n = int(r['n_orders']); ok, no = int(r['random_ok']), int(r['random_refused'] or 0)
    valid = max(n * ok / (ok + no), 1)
    out.append(dict(task=r['task'], line=r['line'], kind=r['kind'], scope=r['scope'], n_orders=n, kept=ok, refused=no, log2_valid=round(math.log2(valid), 3), written=float(r['written']), set_cost=round(float(r['random_mean']) - math.log2(valid), 3)))
with open(f'{D}/set-cost{tail}.tsv.new', 'w') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter='\t'); w.writeheader(); w.writerows(out)
os.replace(f'{D}/set-cost{tail}.tsv.new', f'{D}/set-cost{tail}.tsv')
for s in sorted({r['scope'] for r in out}):
    x = [r for r in out if r['scope'] == s]; m = [r for r in x if r['n_orders'] > 1]
    print(s, 'forms', len(x), 'with several orders', len(m), 'mean log2 valid', round(statistics.mean(r['log2_valid'] for r in m), 2) if m else None, 'mean log2 DAG orders', round(statistics.mean(math.log2(r['n_orders']) for r in m), 2) if m else None,
          'mean change over written', round(statistics.mean(r['set_cost'] - r['written'] for r in m), 2) if m else None, 'under 25 written', sum(r['written'] < 25 for r in x), 'set cost', sum(r['set_cost'] < 25 for r in x), 'all walks refused', none[s])
