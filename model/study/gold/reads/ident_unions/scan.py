import gzip,json,glob,re,sys,os
LIB='/Users/davidlu/code/arc-workspace/engine/lib/registry.sexpr'
GOLD='/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut/view-final/'
ARM='/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/arm/'
OUTD=os.path.dirname(os.path.abspath(__file__))
EVENTS=[]
UNK='?UNK'
JOINED=[]
def parse(text, line0=1):
    """parse all top-level sexps; return [(startline, sexp)]"""
    toks=[];line=line0;i=0;n=len(text)
    while i<n:
        c=text[i]
        if c=='\n': line+=1;i+=1
        elif c in ' \t\r': i+=1
        elif c==';':
            while i<n and text[i]!='\n': i+=1
        elif c in '()': toks.append((c,line));i+=1
        elif c=='"':
            j=i+1
            while text[j]!='"': j+=1
            toks.append((text[i:j+1],line));i=j+1
        else:
            j=i
            while j<n and text[j] not in ' \t\r\n()': j+=1
            toks.append((text[i:j],line));i=j
    out=[];stack=[];start=None
    for t,l in toks:
        if t=='(':
            if not stack: start=l
            stack.append([])
        elif t==')':
            x=stack.pop()
            if stack: stack[-1].append(x)
            else: out.append((start,x))
        else:
            if stack: stack[-1].append(t)
    return out
def unparse(x):
    return x if isinstance(x,str) else '('+' '.join(unparse(y) for y in x)+')'
# ---- registry
reg=parse(open(LIB).read())
COMP={};PROP={};LIBREL=set();FROMKEY=set()
def cols(items):
    r=[]
    for it in items:
        if isinstance(it,list) and len(it)==2 and all(isinstance(z,str) for z in it): r.append(tuple(it))
    return r
for _,f in reg:
    if f[0]=='component':
        tp=[p if isinstance(p,str) else p[0] for p in next(x for x in f if isinstance(x,list) and x and x[0]=='type-parameters')[1:]]
        ins={};outs={}
        for sec in f:
            if isinstance(sec,list) and sec and sec[0]=='inputs':
                for it in sec[1:]:
                    ins[it[0]]=cols(it[1:])
                    if 'from-key' in it: FROMKEY.add((f[1],it[0]))
            if isinstance(sec,list) and sec and sec[0]=='outputs':
                for it in sec[1:]: outs[it[0]]=cols(it[1:])
        COMP[f[1]]=(tp,ins,outs)
    elif f[0]=='proposer':
        c=next((x for x in f if isinstance(x,list) and x and x[0]=='columns'),None)
        PROP[f[1]]=cols(c[1:]) if c else []
    elif f[0]=='relation': LIBREL.add(f[1])
FACT={'input','ex_input','ex_output'}
SPECIAL={'OR','IF','ALL','NOT','=','!=','<','<=','>','>='}
def lab(s): return s.lstrip('*^')
def isvar(s): return isinstance(s,str) and re.match(r'^[*^]?[A-Za-z]\w*$',s) is not None
class Ctx:
    def __init__(s): s.cat={}; s.opaque=set(); s.uid=0
def site_args(site):
    """site (:Col args...) or bare label -> (col, [ (field or None, label) ], recordflag)"""
    if isinstance(site,str): return lab(site),[(None,lab(site))]
    col=site[0].lstrip(':'); args=[]
    for a in site[1:]:
        if isinstance(a,str):
            if re.match(r'^[*^]?[A-Za-z]\w*$',a): args.append((None if col!='key' else lab(a),lab(a)))
        elif isinstance(a,list) and a and isinstance(a[0],str) and a[0].startswith(':'):
            f=a[0].lstrip(':'); sub=[x for x in a[1:] if isinstance(x,str) and isvar(x)]
            for x in sub: args.append((f,lab(x)))
    return col,args
def colsrc(ctx,rel,col,field):
    """sources (frozenset) of column of relation; UNK marker as {UNK}"""
    if not rel.startswith('&') or rel in FACT: return frozenset()
    if rel in ctx.opaque: return frozenset([UNK])
    c=ctx.cat.get(rel)
    if c is None: return frozenset([UNK])
    v=c.get(col)
    if v is None: return frozenset([UNK]) if c.get('__open__') else frozenset()
    if isinstance(v,dict):
        if field is None: return frozenset().union(*v.values()) if v else frozenset()
        return v.get(field,frozenset())
    return v
class Analysis:
    def __init__(s,ctx,seed=None):
        s.ctx=ctx;s.occ=[];s.eq=[];s.n=0
        if seed:
            for v,sr in seed.items(): s.occ.append((v,sr,{},'(key)'))
    def atoms(s,atoms,path):
        for a in atoms: s.atom(a,path)
    def atom(s,a,path):
        if not isinstance(a,list) or not a: return
        h=a[0]
        if h=='NOT': s.atom(a[1],path) if len(a)>1 else None
        elif h=='OR':
            s.n+=1;i=s.n
            for b,br in enumerate(a[1:]):
                p=dict(path);p[i]=b;s.atoms(b_atoms(br),p)
        elif h=='IF':
            s.n+=1;i=s.n
            p=dict(path);p[i]=0;s.atoms(a[1],p);s.atoms(a[2],p)
            p=dict(path);p[i]=1;s.atoms(a[3],p) if len(a)>3 else None
        elif h=='ALL':
            s.atoms(a[1],path);s.atoms(a[2],path)
        elif h in ('ONE','SET','CHOOSE'): pass
        elif h in ('=','!=','<','<=','>','>='):
            if len(a)==3 and isvar(a[1]) and isvar(a[2]): s.eq.append((h,lab(a[1]),lab(a[2]),path,unparse(a)))
        else:
            rel=h;txt=unparse(a)
            for site in a[1:]:
                if isinstance(site,str) and not isvar(site): continue
                col,args=site_args(site)
                for f,l in args:
                    s.occ.append((l,colsrc(s.ctx,rel,col,f),path,txt))
    def vars(s):
        d={}
        for v,sr,p,t in s.occ: d.setdefault(v,set()).update(sr)
        for h,a,b,p,t in s.eq:
            if h=='=':
                d.setdefault(a,set()).update(d.get(b,()));d.setdefault(b,set()).update(d.get(a,()))
        return {k:frozenset(x-{UNK}) for k,x in d.items()}
    def violations(s):
        res=[]
        by={}
        for o in s.occ: by.setdefault(o[0],[]).append(o)
        groups=[(v,[(o[1],o[2],o[3]) for o in os_]) for v,os_ in by.items()]
        # eq/ne comparisons: join of the two vars' occurrences
        for h,a,b,p,t in s.eq:
            if h in ('=','!='):
                oa=[(o[1],o[2],o[3]) for o in by.get(a,[])];ob=[(o[1],o[2],o[3]) for o in by.get(b,[])]
                groups.append((f'{a}{h}{b}',oa+[(x,pp,tt) for x,pp,tt in ob]+[]))
        for v,os_ in groups:
            res.extend(check(v,os_))
        return res
def b_atoms(br):
    return br
def conj(p,q):
    return all(q[k]==p[k] for k in p if k in q)
def check(v,os_):
    """os_: list of (srcset,path,text). returns list of finding dicts"""
    out=[]
    idn=[o for o in os_ if (o[0]-{UNK})]
    unk=[o for o in os_ if UNK in o[0]]
    if len(os_)<2: return out
    cross=None;multi=False;unres=False
    for i in range(len(os_)):
        for j in range(i+1,len(os_)):
            a,b=os_[i],os_[j]
            if not conj(a[1],b[1]): continue
            sa,sb=a[0]-{UNK},b[0]-{UNK}
            if (UNK in a[0] and sb) or (UNK in b[0] and sa): unres=True;
            if sa and sb:
                JOINED.append((v,sorted(sa),sorted(sb),a[2]))
                if len(sa)>1 or len(sb)>1: multi=True
                if not (sa&sb) and cross is None: cross=(a,b)
                elif sa!=sb and not cross: multi=True
    if cross:
        out.append(dict(kind='cross',var=v,a=sorted(cross[0][0]),b=sorted(cross[1][0]),atom_a=cross[0][2],atom_b=cross[1][2],multi=multi))
    elif multi:
        a=[o for o in idn][0];
        out.append(dict(kind='multi',var=v,srcs=sorted(set().union(*[o[0] for o in idn])),atoms=[o[2] for o in idn][:3]))
    elif unres:
        out.append(dict(kind='unresolved',var=v,srcs=sorted(set().union(*[o[0] for o in idn])),atoms=[o[2] for o in os_][:3]))
    return out
def srcs(x): return x-{UNK}
def mixed_of(c):
    """c: col -> frozenset or dict(field->frozenset). returns {col or col.field: sorted sources} with >=2 sources"""
    r={}
    for col,v in c.items():
        if col=='__open__': continue
        if isinstance(v,dict):
            for f,s in v.items():
                if len(srcs(s))>=2: r[col+'.'+f]=sorted(srcs(s))
        elif len(srcs(v))>=2: r[col]=sorted(srcs(v))
    return r
def reads_mixed(analyses):
    out=set()
    for a in analyses:
        for v,sr,p,t in a.occ:
            if len(srcs(sr))>=2 and t!="(key)": out.add(t)
    return out
def merge(old,new):
    if old is None: return new
    r=dict(old)
    for k,v in new.items():
        if k not in r: r[k]=v
        elif isinstance(v,dict) and isinstance(r[k],dict):
            m=dict(r[k])
            for f,s in v.items(): m[f]=m.get(f,frozenset())|s
            r[k]=m
        elif isinstance(v,frozenset) and isinstance(r[k],frozenset): r[k]=r[k]|v
    return r
def analyze_program(text):
    ctx=Ctx();findings=[];ctx.defs={};ctx.redef=[];ctx.rigid=[];ctx.rigid_read=set()
    forms=parse(text)
    ev=[]   # events: (line, formtext, mixedcols, readsmixed(list), role)
    def setcat(name,c,ln):
        if name in ctx.cat and name in ctx.defs: ctx.redef.append((name,ln))
        ctx.cat[name]=merge(ctx.cat.get(name),c) if name in ctx.defs else c
    for ln,f in forms:
        h=f[0]
        try:
            if h in('RULE','DET'):
                name=f[1];body=f[2:]
                ctx.defs[name]=ln
                if h=='DET' and len(body)==1 and isinstance(body[0],str):
                    pc=PROP.get(body[0])
                    if pc is None: ctx.opaque.add(name); continue
                    setcat(name,{c:(frozenset([name]) if t=='Ident' else frozenset()) for c,t in pc},ln)
                    continue
                if not body: ctx.cat[name]={}; continue
                a=Analysis(ctx);a.atoms(body,{})
                for r in a.violations(): findings.append((ln,f,r))
                c=a.vars();setcat(name,c,ln)
                mc=mixed_of(ctx.cat[name]);rm=reads_mixed([a])
                if mc or rm: ev.append((ln,unparse(f),mc,sorted(rm),h))
            elif h=='INIT':
                name=f[1];comp=f[2]
                ctx.defs[name]=ln
                tp,ins,outs=COMP[comp]
                rest=f[3:]
                keyb=None;keyinputs=[];inputs=[];ans=[]
                for it in rest:
                    if isinstance(it,list) and it and it[0]=='key': keyb=it[1];keyinputs=it[2:]
                    else: inputs.append(it)
                keysrc={}
                if keyb is not None:
                    ka=Analysis(ctx);ka.atoms(keyb,{});ans.append(ka)
                    for r in ka.violations(): findings.append((ln,['INIT',name,comp,'(key ...)'],r))
                    kv=ka.vars()
                    keynames=[]
                    def walk(x):
                        if isinstance(x,str):
                            if x.startswith('^'): keynames.append(x[1:])
                        else:
                            for y in x: walk(y)
                    walk(keyb)
                    for k in keynames: keysrc[k]=kv.get(k,frozenset())
                param={p:set() for p in tp}
                seed=dict(keysrc)
                def mkout():
                    for oname,ocols in outs.items():
                        c={}
                        for cn,t in ocols:
                            if cn=='key': c['key']=dict((k,frozenset(v)) for k,v in keysrc.items())
                            elif t in param: c[cn]=frozenset(param[t])
                            elif t=='Ident': c[cn]=frozenset([name])
                            else: c[cn]=frozenset()
                        ctx.cat[name+'.'+oname]=c
                nb=len(ans)
                for _pass in range(2 if comp=='Unfold' else 1):
                    mkout();del ans[nb:];findings_n=len(findings)
                    for inp in keyinputs+inputs:
                        iname=inp[0];head=inp[1] if len(inp)>1 else [];body=inp[2:]
                        a=Analysis(ctx,seed);a.atoms(body,{});ans.append(a)
                        for r in a.violations(): findings.append((ln,['INIT',name,comp,unparse(inp)],r))
                        vs=a.vars()
                        spec=dict(ins.get(iname,[]))
                        for hs in head:
                            col,args=site_args(hs)
                            t=spec.get(col)
                            if t in param:
                                for fld,l in args: param[t].update(vs.get(l,()))
                own={}
                for k,v in keysrc.items():
                    if len(srcs(v))>=2: own['key.'+k]=sorted(srcs(v))
                for t,v in param.items():
                    if len(srcs(v))>=2: own['param '+t]=sorted(srcs(v))
                for iname,icols in ins.items():
                    if iname in outs: continue
                    has=any(i[0]==iname for i in keyinputs+inputs)
                    c={}
                    for cn,t in icols:
                        if cn=='key': c['key']=dict((k,frozenset(v)) for k,v in keysrc.items())
                        elif t in param:
                            if not has and t!='Point': c[cn]=(frozenset().union(*keysrc.values()) if keysrc else frozenset()) if (comp,iname) in FROMKEY else frozenset()
                            else: c[cn]=frozenset(param[t])
                        elif t=='Ident': c[cn]=frozenset([name])
                        else: c[cn]=frozenset()
                    ctx.cat[name+'.'+iname]=c
                    if not has and (comp,iname) in FROMKEY:
                        m=mixed_of({k:v for k,v in c.items() if k!='key'})
                        for k,v in m.items(): own['fromkey '+iname+'.'+k]=v
                for oname,ocols in outs.items():
                    c={}
                    for cn,t in ocols:
                        if cn=='key': c['key']=dict((k,frozenset(v)) for k,v in keysrc.items())
                        elif t in param: c[cn]=frozenset(param[t])
                        elif t=='Ident': c[cn]=frozenset([name])
                        else: c[cn]=frozenset()
                    ctx.cat[name+'.'+oname]=c
                rm=reads_mixed(ans)
                if own or rm: ev.append((ln,unparse(f),own,sorted(rm),'INIT'))
            elif h=='CHOOSE':
                a=Analysis(ctx)
                for part in f[2:]:
                    if isinstance(part,list) and part and part[0] in ('for','from'): a.atoms(part[1:],{})
                for r in a.violations(): findings.append((ln,f,r))
                ctx.defs[f[1]]=ln
                setcat(f[1],a.vars(),ln)
                mc=mixed_of(ctx.cat[f[1]]);rm=reads_mixed([a])
                if mc or rm: ev.append((ln,unparse(f),mc,sorted(rm),h))
            elif h=='RIGID_DET':
                name=f[1];ctx.rigid.append((ln,name));ctx.defs[name]=ln
                items=f[2:];ans=[];lab_src={}
                keyl=[];instl=[]
                def carets(x,acc):
                    if isinstance(x,str):
                        if x.startswith('^'): acc.append(x[1:])
                    else:
                        for y in x: carets(y,acc)
                if items and isinstance(items[0],list) and items[0] and items[0][0]=='key':
                    kb=items[0][1];items=items[0][2:]
                    ka=Analysis(ctx);ka.atoms(kb,{});ans.append(ka);kv=ka.vars();carets(kb,keyl)
                    for k in keyl: lab_src[k]=kv.get(k,frozenset())
                if items and isinstance(items[0],list) and items[0] and items[0][0]=='instance':
                    ib=items[0][1];items=items[0][2:]
                    ia=Analysis(ctx,dict(lab_src));ia.atoms(ib,{});ans.append(ia);iv=ia.vars();carets(ib,instl)
                    for k in instl: lab_src[k]=iv.get(k,frozenset())
                keyd=dict((k,lab_src[k]) for k in keyl)
                outc={}
                for part in items:
                    if not(isinstance(part,list) and part and isinstance(part[0],str) and part[0].startswith('&')): continue
                    pa=Analysis(ctx,dict(lab_src));pa.atom(part,{});ans.append(pa)
                    pv=pa.vars()
                    c={k:v for k,v in pv.items() if k not in lab_src}
                    if keyd: c['key']=dict(keyd)
                    ctx.cat[name+'.'+part[0][1:]]=c
                    outc.update({k:v for k,v in c.items() if k!='key'})
                pc={k:lab_src[k] for k in instl}
                if keyd: pc['key']=dict(keyd)
                ctx.cat[name+'.pose']=pc
                mc=mixed_of(outc);mc.update(mixed_of({k:v for k,v in pc.items() if k!='key'}))
                for k,v in keyd.items():
                    if len(srcs(v))>=2: mc['key.'+k]=sorted(srcs(v))
                rm=reads_mixed(ans)
                if mc or rm: ev.append((ln,unparse(f),mc,sorted(rm),'RIGID_DET'))
            elif h=='OUT':
                a=Analysis(ctx)
                for at in f[1:]: a.atom(at,{})
                rm=reads_mixed([a])
                if rm: ev.append((ln,unparse(f),{},sorted(rm),'OUT'))
        except Exception as e:
            findings.append((ln,f,dict(kind='error',msg=repr(e))))
    ctx.ev=ev;ctx.formtext={}
    for ln,f in forms:
        if f[0] in('RULE','DET','INIT','CHOOSE','RIGID_DET') and len(f)>1: ctx.formtext.setdefault(f[1],(ln,unparse(f)))
    return findings,forms,ctx
def root_of(s):
    return s.split('.')[0]
def task_row(stem,sname,text):
    fs,forms,ctx=analyze_program(text)
    errs=[dict(line=ln,msg=r.get('msg')) for ln,f,r in fs if r['kind']=='error']
    origins=[];down=[]
    for ln,ft,mc,rm,h in ctx.ev:
        if mc and not rm: origins.append((ln,ft,mc,h))
        elif mc or rm: down.append((ln,ft,mc,h))
        # (a form that reads a mixed column but has no mixed own column is still downstream)
    # a form with mixed own columns that also reads mixed columns is downstream
    rig=ctx.rigid
    rigread=0
    for ln,nm in rig:
        pref=nm
        hit=False
        for ln2,f in forms:
            if ln2>ln and (pref+'.' in unparse(f) or '('+pref+' ' in unparse(f) or '('+pref+')' in unparse(f)): hit=True;break
        rigread+=hit
    row=dict(stem=stem,set=sname,n_forms=len(forms),n_mixed_events=len(ctx.ev),
        origins=[],downstream_count=len(down),downstream_lines=[d[0] for d in down],
        redefined=ctx.redef,rigid_forms=len(rig),rigid_read=rigread,errors=errs)
    for ln,ft,mc,h in origins:
        srcset=sorted({root_of(s) for v in mc.values() for s in v})
        row['origins'].append(dict(line=ln,form=ft,kind=h,columns=mc,sources=srcset,
            source_texts={s:ctx.formtext.get(s,(None,None))[1] for s in srcset},
            downstream_after=sum(1 for d in down if d[0]>ln)))
    return row
if __name__=='__main__':
    held=set(open(ARM+'held-tasks.txt').read().split());ev=set(open(ARM+'eval-tasks.txt').read().split())
    stems=sorted(os.listdir(GOLD))
    if sys.argv[1:2]==['one']:
        for s in sys.argv[2:]:
            r=json.loads(gzip.open(GOLD+s+'/pairs.jsonl.gz','rt').readline())
            print(json.dumps(task_row(s,'?',r['gold_sexp']),indent=1))
        sys.exit()
    n=0
    with open(OUTD+'/rows.jsonl','w') as out, open(OUTD+'/stems.txt','w') as st:
        for s in stems:
            r=json.loads(gzip.open(GOLD+s+'/pairs.jsonl.gz','rt').readline())
            tag='held' if s in held else ('eval-only' if s in ev else 'train')
            row=task_row(s,tag,r['gold_sexp'])
            out.write(json.dumps(row)+'\n')
            if row['origins']: st.write(s+'\n');n+=1
    print('stems with mixing',n)
