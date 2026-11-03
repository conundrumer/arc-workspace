import json,collections,random,os
H=os.path.dirname(os.path.abspath(__file__))
R=[json.loads(l) for l in open(H+'/join.jsonl')]
print('tasks',len({r['task'] for r in R}),'rows',len(R),'gold',sum(r['gold'] for r in R))
N={0:'mixed: keeps no parent',1:'narrows a parent',2:'keeps a parent, widens rows',3:'keeps a parent, adds columns',4:'same rows as a parent'}
g=[r for r in R if r['gold']];j=[r for r in R if not r['gold']]
for k in N:
    a=sum(r['join']==k for r in j)/len(j);b=sum(r['join']==k for r in g)/max(len(g),1)
    print('  %-30s junk %.3f gold %.3f'%(N[k],a,b))
def q(v):
    v=sorted(v);return [round(v[int(len(v)*p)],3) for p in (.25,.5,.75)] if v else []
print('narrows, share of parent kept: junk',q([r['kept'] for r in j if r['join']==1]),'gold',q([r['kept'] for r in g if r['join']==1]))
print('columns: junk',q([r['columns'] for r in j]),'gold',q([r['columns'] for r in g]))
random.seed(2)
for k in (0,3,4):
    print(N[k])
    v=[r for r in j if r['join']==k]
    for r in random.sample(v,min(5,len(v))): print('   ',r['clause'][:150])
print('gold')
for r in g[:12]: print('   ',r['join'],r['kept'],r['clause'][:130])
