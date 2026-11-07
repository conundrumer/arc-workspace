"""The draw records of a job: draws.jsonl while its worker writes them, draws.jsonl.zst once the job has ended."""
import json
import subprocess
from pathlib import Path


def has_draws(job):
    job = Path(job)
    return (job / 'draws.jsonl.zst').exists() or (job / 'draws.jsonl').exists()


def draws(job):
    """The records of a job's draws, in order; none where it has no record file. The zstd command reads the stream, so any Python can read it."""
    job = Path(job)
    if (job / 'draws.jsonl.zst').exists():
        with subprocess.Popen(['zstd', '-dcq', str(job / 'draws.jsonl.zst')], stdout=subprocess.PIPE, text=True, encoding='utf-8') as p:
            yield from map(json.loads, p.stdout)
    elif (job / 'draws.jsonl').exists():
        with open(job / 'draws.jsonl', encoding='utf-8') as f:
            yield from map(json.loads, f)


def compress(job):
    """Turns a finished job's draws.jsonl into draws.jsonl.zst."""
    path = Path(job) / 'draws.jsonl'
    if path.exists():
        subprocess.run(['zstd', '-q', '-3', '--rm', '-f', str(path)], check=True)
