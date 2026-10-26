"""This script exists so that the copy of `merge_steps.py` on `master`, which
runs `scripts/gate.py --affected <base> <out>` and `scripts/gate.py --adopt
<out>`, finds it while the change that deletes the gate merges. It reads no
argument and exits 0."""
