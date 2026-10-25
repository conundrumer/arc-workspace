"""Writes lm/_pretrain_profile.py: pretrain.py with step 3 under torch.profiler, and each step's seconds printed.

Step 3 is profiled on CUDA only. Its report gives the wall time, the CUDA self time by group (attention, matmul,
elementwise/other), the 25 CUDA kernels of most self time and the 10 CPU ops of most self time, each line
starting with `PROFILE`; every step prints a line `STEP_SECONDS <step> <seconds>`. The script asserts that
each of its two edits finds its anchor in pretrain.py exactly once. Run the written file as pretrain.py is run.

    python lm/make_profile.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "pretrain.py").read_text()

old1 = "        drawn, cost = draw(train, a.programs, a.step_rows)\n        with autocast():\n"
new1 = ("        drawn, cost = draw(train, a.programs, a.step_rows)\n"
        "        prof = None\n"
        "        if step == 3 and a.device == 'cuda':\n"
        "            torch.cuda.synchronize()\n"
        "            prof = torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA], record_shapes=True, with_stack=False)\n"
        "            prof.__enter__()\n"
        "            t = time.time()\n"
        "        with autocast():\n")
assert src.count(old1) == 1
src = src.replace(old1, new1)

old2 = "        step_seconds.append(time.time() - t)\n"
new2 = ("        if prof is not None:\n"
        "            torch.cuda.synchronize()\n"
        "        step_seconds.append(time.time() - t)\n"
        "        print(f'STEP_SECONDS {step} {step_seconds[-1]:.3f} (profiled)' if prof is not None else f'STEP_SECONDS {step} {step_seconds[-1]:.3f}', flush=True)\n"
        "        if prof is not None:\n"
        "            prof.__exit__(None, None, None)\n"
        "            report(prof, step_seconds[-1])\n")
assert src.count(old2) == 1
src = src.replace(old2, new2)

report = '''

def report(prof, wall):
    ev = prof.key_averages()
    dev = lambda e: getattr(e, "self_device_time_total", None) if getattr(e, "self_device_time_total", None) is not None else getattr(e, "self_cuda_time_total", 0)
    kernels = [e for e in ev if dev(e) > 0 and e.device_type == torch.autograd.DeviceType.CUDA]
    kernels.sort(key=dev, reverse=True)
    total = sum(dev(e) for e in kernels)
    def group(name):
        n = name.lower()
        if any(k in n for k in ("sdpa", "efficient_attention", "flash", "flex", "fmha", "attention")):
            return "attention"
        if any(k in n for k in ("gemm", "cutlass", "cublas", "matmul", "sgemm", "wgmma", "ampere_")):
            return "matmul"
        return "elementwise/other"
    groups = {}
    for e in kernels:
        groups[group(e.key)] = groups.get(group(e.key), 0) + dev(e)
    cpu_total = sum(e.self_cpu_time_total for e in ev)
    print(f"PROFILE step wall {wall:.3f} s; CUDA self time total {total / 1e6:.3f} s; CPU self time total {cpu_total / 1e6:.3f} s")
    for g, v in sorted(groups.items(), key=lambda x: -x[1]):
        print(f"PROFILE group {g}: {v / 1e6:.3f} s ({100 * v / max(total, 1):.1f}%)")
    for e in kernels[:25]:
        print(f"PROFILE kernel {dev(e) / 1e3:10.1f} ms  x{e.count:<6d} [{group(e.key)}] {e.key[:150]}")
    print("PROFILE top CPU ops by self time")
    for e in sorted(ev, key=lambda e: e.self_cpu_time_total, reverse=True)[:10]:
        print(f"PROFILE cpu {e.self_cpu_time_total / 1e3:10.1f} ms  x{e.count:<6d} {e.key[:100]}")

'''
src = src.replace("\ndef main():", report + "\ndef main():", 1)
(HERE / "_pretrain_profile.py").write_text(src)
