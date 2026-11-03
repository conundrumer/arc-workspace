import glob,os,pickle
P='/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/port'; D='/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/39487d30-036f-4e4b-ad99-183af6a33661/scratchpad/lanes/results/features-port-rows'
os.makedirs('merged',exist_ok=True)
for e in os.scandir('merged'): os.remove(e.path)
held={tuple(l.split()) for l in open('forms.txt')}
n=[0,0,0]
for f in glob.glob('prows/*.pkl'):
    b=os.path.basename(f); t,i,_=b.split('.')
    if (t,i) not in held and not os.path.exists(f'{D}/features-port-rows-fit-8s/{b}'):
        os.symlink(os.path.abspath(f),'merged/'+b); n[0]+=1
for f in glob.glob(D+'/features-port-rows-fit-8s/*.pkl'):
    os.symlink(f,'merged/'+os.path.basename(f)); n[1]+=1
for f in glob.glob(D+'/features-port-rows-heldout-60s/*.pkl'):
    os.symlink(f,'merged/'+os.path.basename(f)); n[2]+=1
print('fit mac',n[0],'fit pod',n[1],'held pod',n[2])
