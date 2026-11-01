"""A relcheap plugin: the features of rk3_def.py on a row with no marks (dagset.view), with a prefix's labels read as a set of atoms (dagset.rel_labels), and rk4o."""
import os
import sys

C = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, C)
import dagset  # noqa: E402
import relfeat  # noqa: E402

R = dagset.R
rk3 = dagset.load(f'{R}/rk3_def.py', 'rk3_def_dag')
abc = dagset.load(f'{R}/rk1_abc.py', 'rk1_abc_dag')
FEATURE_FUNCS = dict(rk3.FEATURE_FUNCS)
FEATURE_FUNCS.update(struct=relfeat.f_struct, b=relfeat.f_b, ctx=relfeat.f_tree_ctx, rk3o=dagset.rk3o.FEATURE_FUNCS['rk3o'])
c1 = dagset.load(f'{R}/features/rk1c.py', 'rk1c_dag')
c1._labels = dagset.rel_labels
FEATURE_FUNCS['rk1c'] = abc._keep(c1.FEATURE_FUNCS['rk1c'])
d = dagset.load(f'{R}/features/rk2d.py', 'rk2d_dag')
d._c1._labels = dagset.rel_labels
FEATURE_FUNCS['rk2d'] = d.FEATURE_FUNCS['rk2d']
f = dagset.load(f'{C}/features/rk2f.py', 'rk2f_dag')
f._labels = dagset.rel_labels
FEATURE_FUNCS['rk2f'] = f.FEATURE_FUNCS['rk2f']
FEATURE_FUNCS['rk4o'] = dagset.load(f'{C}/features/rk4o.py', 'rk4o').FEATURE_FUNCS['rk4o']
FEATURE_FUNCS = {g: dagset.on_view(fn) for g, fn in FEATURE_FUNCS.items()}
