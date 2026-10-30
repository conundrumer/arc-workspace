"""Framed file transport for the native normalization audit, not evaluation.

The native audit sends records over a pipe. Only JsonlWriter owns the file.
Existing plain/gzip files remain readable through the shared reader; a native
restart writes a NEW explicit .jsonl.zst output, never converts a finished file.
"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from judge3.framed_jsonl import JsonlReader, JsonlWriter, iter_json


def send(value):
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def main():
    path = Path(sys.argv[1])
    with JsonlWriter(path) as out:
        # Complete orphan frames have already been recovered by the writer.
        # Only committed records can seed the native acquisition-key lookup.
        send(dict(event='opened', committed_lines=out.committed_lines))
        # Optional finished results are read through the same legacy-aware
        # reader, never converted or appended. Native acquisition keys decide
        # whether each record is reusable; this transport makes no verdict.
        for previous in json.loads(os.environ.get('GOLD_PRUNE_REUSE_JSONL', '[]')):
            if Path(previous).resolve() == path.resolve():
                raise ValueError('reuse input must be distinct from output')
            for row in iter_json(previous):send(dict(event='previous_external', row=row))
        seen = 0
        with JsonlReader(path) as source:
            for raw in source.iter_lines(stop_line=out.committed_lines + 1):
                send(dict(event='previous', row=json.loads(raw))); seen += 1
        if seen != out.committed_lines:
            raise ValueError('normalization audit committed record count differs')
        send(dict(event='ready'))
        for raw in sys.stdin:
            out.write(json.loads(raw))
            # Each native comparison is an expensive restart unit. Commit it
            # before acknowledging; never recompute an acknowledged result.
            out.flush()
            send(dict(event='committed', committed_lines=out.committed_lines))


if __name__ == '__main__':
    main()
