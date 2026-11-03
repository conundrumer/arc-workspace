"""Runs each line of a job file as a shell command, at most P at once. A rerun of a fit resumes from its state file.

  fit_jobs.py JOBS P LOG
"""
import concurrent.futures, subprocess, sys, time

jobs, procs, log = open(sys.argv[1]).read().splitlines(), int(sys.argv[2]), sys.argv[3]
t0 = time.time()


def run(pair):
    i, cmd = pair
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    with open(log, 'a') as f:
        f.write(f'{time.time() - t0:.0f}s job {i + 1}/{len(jobs)} rc {r.returncode} {cmd.split(" -I ")[-1]}\n{r.stdout[-400:]}{r.stderr[-400:]}\n')
    return r.returncode


with concurrent.futures.ThreadPoolExecutor(procs) as pool:
    codes = list(pool.map(run, enumerate(jobs)))
print('done', len(codes), 'failed', sum(c != 0 for c in codes), round(time.time() - t0), 's', flush=True)
