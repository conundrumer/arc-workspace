import sys,json,gzip
sys.argv=['x']
exec(open('scan.py').read().split("if __name__=='__main__':")[0])
base=json.loads(gzip.open(GOLD+'e872b94a/pairs.jsonl.gz','rt').readline())['gold_sexp'].split('\n')
i=next(k for k,l in enumerate(base) if l.startswith('(OUT'))
cases={
 'A param (Quotient equivalent a from two sources)':['(INIT &p1 Quotient (equivalent ((:a Id) (:b Id2)) (&r3.component (:Id *Id) (:P *P)) (&r8.component (:Id *Id2) (:P P))) (edge ((:a Id3) (:b Id4)) (&r8.component (:Id *Id3)) (&r3.component (:Id *Id4))))'],
 'B key mixes two sources':['(INIT &p1 Cardinality (key ((OR ((&r3.component (:Id ^Id) (:P *P))) ((&r8.component (:Id Id) (:P P)))))) (member ((:m P2)) (&r3.component (:Id Id) (:P *P2))))'],
 'C helper via CHOOSE/RULE twice (same name defined twice)':['(RULE &p1 (&r3.component (:Id *Id)))','(RULE &p1 (&r8.component (:Id *Id)))','(RULE &p2 (&p1 (:Id *Id)))'],
 'D INIT output echo -> helper':['(INIT &p1 Cardinality (member ((:m Id)) (OR ((&r3.component (:Id *Id))) ((&r8.component (:Id Id)))))  (domain () (&r0)))','(RULE &p2 (&p1.size (:key *K) (:N *N)))'],
}
for k,add in cases.items():
    lines=base[:i]+add+base[i:]
    fs,forms,ctx=analyze_program('\n'.join(lines))
    print(k); print('  origins:',[(ln,mc) for ln,ft,mc,rm,h in ctx.ev if mc and not rm and ln>=i], 'redef',ctx.redef)
lines=base[:i]+cases['B key mixes two sources']+base[i:]
fs,forms,ctx=analyze_program('\n'.join(lines))
print(ctx.ev[-3:]); print([ (ln,r) for ln,f,r in fs][-3:]); print(unparse(forms[i][1])[:300])
