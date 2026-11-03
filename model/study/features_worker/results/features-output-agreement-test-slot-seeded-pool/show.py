import sys,json
for l in sys.stdin:
    try: d=json.loads(l)
    except Exception: print(l[:500]); continue
    if 'error' in d: print(d); continue
    n=d['node']; print(d['task'],'gold',{k:round(v,2) for k,v in d['gold'].items()},'| node forms',len(n),'mean',round(sum(n.values())/max(len(n),1),2),d['dropped'],d['seconds'])
