import arclog,sys
S=sys.argv[1]+'/rp'
cases,lines=arclog.corpus_tables(S+'/gold',S+'/tasks',task_ids=['1f642eb9'],all_cases=False)
print(lines,len(cases))
c=cases[0]
print(c.case,c.concept,c.dtypes)
for p in ('tables','entries','values'):
    v=getattr(c,p)
    print(p,type(v), list(v.keys())[:40] if hasattr(v,'keys') else [n for n in dir(v) if not n.startswith('_')])
import numpy as np
t=c.tables; e=c.entries
print({k:(len(v) if not isinstance(v,bytes) else 'bytes') for k,v in t.items()})
print({k:(len(v) if not isinstance(v,bytes) else 'bytes') for k,v in e.items()})
print(t['relation_name']); print(t['column_names'][:6]); print(t['column_types'][:6])
print({k:np.frombuffer(v,dtype=c.dtypes['entries.'+k])[:8].tolist() for k,v in e.items() if 'entries.'+k in c.dtypes})
print({k:np.frombuffer(v,dtype=c.dtypes['tables.'+k])[:8].tolist() for k,v in t.items() if 'tables.'+k in c.dtypes})
