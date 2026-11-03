"""Probe: replay one task's gold with the run's kit and engine; print each relation's slot, name and table key columns. Times the steps."""
import json, os, sys, time
t0 = time.time()
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ONE_REPAIR='30', CHOOSE_LIFT='0')
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE]
import live, live_try, superdag as D
from live import M
print('import %.1f s, arclog %s' % (time.time() - t0, live.arclog.__file__), flush=True)
task = sys.argv[1] if len(sys.argv) > 1 else '16b78196'
sampler = live.Sampler(KIT + '/models-tk')
print('sampler %.1f s' % (time.time() - t0), flush=True)
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
forms = [f for f in pe[task].strip().split('\n') if not f.startswith('(OUT')]
sess, d, outs = D.session_of(task)
run = D.Run(sampler.pri, sess, 0, time.monotonic() + 60, d, live.Limits())
run.collect = []
dec, pg = run.scope(forms)
print('replay %.1f s, %d forms, %d tables' % (time.time() - t0, len(forms), len(run.collect)), flush=True)
print('pg attrs', [a for a in dir(pg) if not a.startswith('_')][:60])
print('written', list(pg.written.items())[:12])
print('names', list(getattr(pg, 'names', {}).items())[:12])
for i, ct in enumerate(run.collect[:12]):
    rt = D.relation_tables(ct)
    out = []
    for s, j in rt:
        tb = D.S.parse_table(D.OneTable(ct, j))
        key, ex = D.table_key(tb)
        out.append((s, run.V.name(s) if hasattr(run, 'V') else None, key[0], tb.get('widths'), list(tb.keys())))
    print(i, forms[i][:60], out)
print('---- colmap', type(pg.colmap), list(pg.colmap.items())[:6] if hasattr(pg.colmap, 'items') else pg.colmap)
print('---- colmaps', type(pg.colmaps), list(pg.colmaps.items())[:6] if hasattr(pg.colmaps, 'items') else str(pg.colmaps)[:400])
print('---- record_cols', list(pg.record_cols.items())[:4])
print('---- decl_slots', list(pg.decl_slots.items())[:6])
print('---- decl_types', list(pg.decl_types.items())[:6])
ct = run.collect[7]
for s, j in D.relation_tables(ct):
    tb = D.S.parse_table(D.OneTable(ct, j))
    print(s, pg.names.get('&r%d' % s), tb['labels'], tb['types'], tb['widths'])
