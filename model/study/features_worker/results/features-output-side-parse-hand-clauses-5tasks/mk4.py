import sys
S,T=sys.argv[1:3]
s=open(f'{S}/gold/{T}.arclog').read()
def form(s,head):
    i=s.index(head); d=0
    for j in range(i,len(s)):
        d+= (s[j]=='(')-(s[j]==')')
        if d==0: return i,j+1
    raise SystemExit(head)
# the concept case: every form before the first ALTS, then the tail
a=s.index('(ALTS $cells'); b=s.index('(RULE &ring_cell\n  (&case_copy *M)\n  (input *P)')
s=s[:a]+s[b:]
for h in ('(DET &line','(DET &unfenced','(DET &fence\n','(INIT &least Order','(DET &key_size','(DET &key_corner'):
    i,j=form(s,h); s=s[:i]+s[j:]
i,j=form(s,'(DET &mark_color')
s=s[:i]+'''(DET &common
    (&fence2 *C *K *Col)
    (> K 0)
    (ALL ((ex_output *E))
         ((&fence2 E C K Col))))

  (DET &mark_color
    (&common (:Col *C)))

  (DET &key_size
    (&common *K))

  (DET &key_corner
    (&common (:C *D)))'''+s[j:]
open(f'{S}/{T}/parse/{T}.arclog','w').write(s)
open(f'{S}/{T}/parse/{T}.arcdata','w').write(f';; {T}\n\n(param &key_corner DiagDir (DIAG_TL))\n(param &key_size number (3))\n(param &mark_color Color (5))\n')
