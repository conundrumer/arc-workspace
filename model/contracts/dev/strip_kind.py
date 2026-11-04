"""Dev labeling layer: drops the records of one kind from a variants file, so refeature.py derives them again. The kind `unsettled` names the
variants whose stored values are not the task's.

    python3 strip_kind.py FILE KIND
"""
import json
import sys
from pathlib import Path
import jsonl as J  # noqa: E402

p, kind = Path(sys.argv[1]), sys.argv[2]
drop = (lambda r: r['kind'] != 'base' and r.get('stored', 'same') != 'same') if kind == 'unsettled' else (lambda r: r['kind'] == kind)
keep = [r for r in J.records(p) if not drop(r)]
J.write_all(p, keep)
print(p.name, 'kept', len(keep))
