"""Runs lm/pretrain.py unchanged and prints, at the first clip_grad_norm_ call, the gradient norm of the binding weights."""
import runpy, sys
sys.path.insert(0, "lm")
import torch
import encoder as E

made = []
init = E.FeatureEncoder.__init__
def wrapped(self, *a, **k):
    init(self, *a, **k)
    made.append(self)
E.FeatureEncoder.__init__ = wrapped

clip = torch.nn.utils.clip_grad_norm_
calls = [0]
def clip_wrapped(params, *a, **k):
    calls[0] += 1
    if calls[0] <= 2 and made:
        enc = made[0]
        named = [(n, p) for n, p in enc.named_parameters() if p.requires_grad and ("binding" in n or "ptr_bind" in n)]
        norms = {n: (float(p.grad.norm()) if p.grad is not None else None) for n, p in named}
        total = sum(v for v in norms.values() if v is not None)
        print(f"gradcheck: step {calls[0]}: {len(named)} binding tensors, {sum(v is None for v in norms.values())} without grad, "
              f"sum of grad norms {total:.6g}, largest {max((v for v in norms.values() if v is not None), default=0):.6g}", flush=True)
    return clip(params, *a, **k)
torch.nn.utils.clip_grad_norm_ = clip_wrapped

sys.argv = ["lm/pretrain.py"] + sys.argv[1:]
runpy.run_path("lm/pretrain.py", run_name="__main__")
