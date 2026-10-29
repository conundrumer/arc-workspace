#!/usr/bin/env python3
"""Record real inline-Python/three-command session steps for a human reader.

The step file is an owner's transcript plan, not a model judge call. Commands
execute in order; stdout is copied exactly. Stderr/status stay in the private
execution log rather than the reader's transcript.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time


def record(plan, output, evidence, *, cwd):
    steps = json.loads(Path(plan).read_text())
    rendered = []
    executions = []
    for step in steps:
        start = time.monotonic()
        result = subprocess.run(['zsh', '-c', step['command']], cwd=cwd,
                                text=True, capture_output=True)
        executions.append(dict(step, stdout=result.stdout, stderr=result.stderr,
                               returncode=result.returncode, seconds=time.monotonic()-start))
        rendered.append(step['purpose'] + '\n\n```sh\n' + step['command'].rstrip() + '\n```\n\n'
                        + '```text\n' + result.stdout.rstrip('\n') + '\n```\n')
        if result.returncode:
            # Preserve a failed actual attempt, never fabricate its output.
            break
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(evidence).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text('\n'.join(rendered))
    Path(evidence).write_text(json.dumps(executions, ensure_ascii=False, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    args = parser.parse_args()
    record(args.steps, args.output, args.evidence, cwd=args.cwd)


if __name__ == '__main__':
    main()
