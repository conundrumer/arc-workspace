"""Covers of gold forms per arm at equal samples: on each task, each arm counts covers up to the smallest sample count of any arm there. Split by gold DAG depth, non-DET apart."""
import collections, glob, json, os, re
R='work/lm/data-study/sampler/runs/'
ARMS={'stub':'superdag1','full':'superdag2','base':'superdag3','p2':'/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/policy2/arm/p2'}
N=re.compile(r'&[A-Za-z_]\w*')
gold={}
for sp in json.load(open(R+'pool1/points.json')):
    d={}; dep=[]; k=[]
    for l in sp['gold_sexp'].strip().split('\n'):
        if l.startswith('(OUT'): continue
        h=l.split()[1]; d[h]=1+max([d[m] for m in N.findall(l) if m in d and m!=h],default=0)
        dep.append(d[h]); k.append(l[1:l.index(' ')])
    gold[sp['task']]=(dep,k)
done={a:{os.path.basename(f)[:-10] for f in glob.glob((p if p[0]=='/' else R+p)+'/*.done.json')} for a,p in ARMS.items()}
tasks=sorted(set.intersection(*done.values()))
B=[(1,1,'1'),(2,3,'2-3'),(4,6,'4-6'),(7,99,'7+')]
bucket=lambda x: next(n for a,b,n in B if a<=x<=b)
ev={}
for a,p in ARMS.items():
    for t in tasks:
        draws=0; cov=[]; secs=0
        for l in open((p if p[0]=='/' else R+p)+'/'+t+'.events.jsonl'):
            e=json.loads(l)
            if e['event']=='cover': cov.append(e)
            if e['event']=='done': draws=e['draws']; secs=e.get('seconds',0)
        ev[a,t]=(draws,cov,secs)
tot=collections.Counter()
for t in tasks:
    for x,y in zip(*gold[t]): tot[bucket(x),y=='DET']+=1
print('tasks',len(tasks),'equal samples total',sum(min(ev[a,t][0] for a in ARMS) for t in tasks))
print('gold non-DET',[(n,tot[n,False]) for *_,n in B],'DET',sum(v for (n,d),v in tot.items() if d))
for a in ARMS:
    got=collections.Counter(); full=collections.Counter(); draws=secs=0
    for t in tasks:
        D=min(ev[b,t][0] for b in ARMS); dep,k=gold[t]; s1=set(); s2=set()
        n,cov,sc=ev[a,t]; draws+=n; secs+=sc
        for e in cov:
            s2.add(e['gold'])
            if e['draw']<=D: s1.add(e['gold'])
        for i in s1: got[bucket(dep[i]),k[i]=='DET']+=1
        for i in s2: full[bucket(dep[i]),k[i]=='DET']+=1
    nd=lambda c:' '.join('%s:%d'%(n,c[n,False]) for *_,n in B)
    print('%-5s at equal samples non-DET %s DET %d | whole run samples %d, non-DET %s, covers/s %.3f'%(a,nd(got),sum(v for (n,d),v in got.items() if d),draws,nd(full),sum(full.values())/max(secs,1)))
