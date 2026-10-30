"""Shared framed transport for n-prune's finite, ordered metadata outputs."""
from pathlib import Path
from judge3.framed_jsonl import JsonlReader, JsonlWriter, iter_json


def receipt_path(path):
    path = Path(path)
    if path.suffix in ('.zst', '.gz'):
        path = path.with_suffix('')
    return path.with_suffix('.receipt.json')


def write_jsonl(path, records):
    """Continue the same ordered input; never truncate a committed result.

    Expensive acquisitions must resume before calling this metadata writer.
    Validate the committed prefix as well as its length so another source or
    configuration cannot silently append to the same output.
    """
    path=Path(path)
    if not str(path).endswith('.jsonl.zst'):raise ValueError('new pruning JSONL output requires .jsonl.zst')
    require_framed_run(path.parent)
    with JsonlWriter(path) as out:
        committed = out.committed_lines
        previous = iter(iter_json(path))
        count = 0
        for count, record in enumerate(records, 1):
            if count <= committed:
                if next(previous) != record:
                    raise ValueError('framed pruning output source/config prefix differs; use a new output')
            else:
                out.write(record)
        if count < committed:
            raise ValueError('framed pruning output is longer than its source input')
    return Path(path)


def stored_path(path):
    """Actual path for readback/hash receipts, including finished legacy files."""
    path = Path(path)
    if '.jsonl' not in path.name:
        return path
    logical = path.with_suffix('') if path.suffix == '.zst' and not path.exists() else path
    with JsonlReader(logical) as source:
        return source.path


def require_framed_run(directory):
    """Never repurpose a legacy run directory or rewrite its finished files."""
    directory = Path(directory)
    legacy = [p for p in directory.glob('*.jsonl') if not p.name.endswith('.idx.jsonl')]
    legacy += list(directory.glob('*.jsonl.gz'))
    if legacy:
        raise ValueError('legacy JSONL run retained unchanged; use a fresh framed output directory and reuse its records explicitly')
