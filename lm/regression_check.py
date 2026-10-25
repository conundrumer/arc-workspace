"""Checks that train.py without --tables trains as a reference copy does: both run a few steps on the dev data with
the same arguments and seed, as two processes at once, and every train loss and every evaluation must be
identical, to the last digit. By default both use --tiny-base, a small model initialized at random from
SmolLM2-135M's config and tokenizer; --full-model uses SmolLM2-135M itself.

    work/lm/.venv/bin/python lm/regression_check.py [--full-model] [--orig <reference train.py>]
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--orig", default=str(Path(__file__).parent / "reference" / "train_orig.py"),
                help="the reference copy of train.py: the pre-encoder script, which the no-tables path must match")
ap.add_argument("--new", default=str(Path(__file__).parent / "train.py"))
ap.add_argument("--full-model", action="store_true")
ap.add_argument("--timeout", type=int, default=600, help="seconds")
a = ap.parse_args()

args = ["--base", "HuggingFaceTB/SmolLM2-135M", "--data", "lm/data-dev", "--indist", "2", "--minutes", "10",
        "--max-steps", "2", "--eval-train", "--eval-limit", "4", "--budget", "1024", "--max-len", "1024",
        "--device", "cpu"] + ([] if a.full_model else ["--tiny-base"])
env = {**os.environ, "HF_HUB_OFFLINE": "1"}


def outcome(text):
    """The train losses and evaluation rows a run printed, without its timings."""
    rows = []
    for line in text.splitlines():
        if line.startswith("step "):
            rows.append(line.rsplit(" ", 1)[0])          # the elapsed seconds dropped
        elif line.startswith("{"):
            row = json.loads(line)
            row.pop("seconds"); row.pop("device_gb")
            rows.append(row)
    return rows


runs = (("orig", a.orig), ("new", a.new))
with tempfile.TemporaryDirectory() as tmp:
    procs = [subprocess.Popen([sys.executable, "-u", script, *args, "--out", f"{tmp}/{name}"], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for name, script in runs]
    outs = [p.communicate(timeout=a.timeout)[0] for p in procs]
for (name, _), p, out in zip(runs, procs, outs):
    if p.returncode:
        print(f"{name} exited {p.returncode}:\n{out[-3000:]}")
        print("FAIL")
        sys.exit(1)
orig, new = map(outcome, outs)
evals = sum(isinstance(r, dict) for r in orig)
if orig == new and evals:
    print(f"PASS: {len(orig) - evals} train losses and {evals} evaluation rows identical")
    sys.exit(0)
for x, y in zip(orig, new):
    if x != y:
        print(f"first difference:\n  orig {json.dumps(x)[:400]}\n  new  {json.dumps(y)[:400]}")
        break
print(f"FAIL ({len(orig)} rows against {len(new)}, {evals} evaluation rows)")
sys.exit(1)
