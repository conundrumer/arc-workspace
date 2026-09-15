import json
from typing import Any

from arc.jsonio import format_file


def _roundtrip(d: dict[str, Any]) -> Any:
    """Format then re-parse with stdlib; should always succeed and equal."""
    text = format_file(d)
    return json.loads(text)


def test_brace_up_examples():
    d = {
        "train": [
            {"index": 0, "input": [[0, 0]]},
            {"index": 1, "input": [[1, 1]]},
        ]
    }
    text = format_file(d)
    expected = '\n'.join([
        '{',
        '  "train": [{',
        '    "index": 0,',
        '    "input": [',
        '      [0,0]',
        '    ]',
        '  }, {',
        '    "index": 1,',
        '    "input": [',
        '      [1,1]',
        '    ]',
        '  }]',
        '}',
        '',
    ])
    assert text == expected
    assert _roundtrip(d) == d


def test_full_task_file_roundtrips():
    d = {
        "id": "abc12345",
        "source": [
            {"dataset": "arc-agi-1", "split": "evaluation"},
            {
                "dataset": "arc-agi-2",
                "split": "training",
                "perm": {"train": [1, 0, 2]},
            },
        ],
        "comment": "fix something",
        "issue": "https://example.com/issues/1",
        "train": [
            {"index": 0, "input": [[0, 0, 0], [0, 1, 0]], "output": [[1]]},
        ],
        "test": [
            {
                "index": 0,
                "input": [[0]],
                "output": [[1]],
                "alt": {"kind": "rule", "grid": [[2]]},
            }
        ],
    }
    text = format_file(d)
    assert _roundtrip(d) == d
    # spot-check: brace-up used for train
    assert '"train": [{' in text
    # spot-check: grid rows compact
    assert "[0,0,0]" in text


def test_witness_file_roundtrips():
    d = {
        "id": "abc12345",
        "witnesses": [
            {"index": 0, "name": "two colors",
             "hypothesis": "the seam moves", "input": [[1, 2]],
             "output": {"Copy": [[1, 2]], "Flip": None}},
            {"index": 1, "name": "five bands", "hypothesis": "arr_dim is 5",
             "assign": {"arr_dim": [[5]],
                        "tile_d4": [[[0, 2, 0, 2], "D4_LR"]]},
             "input": [[1, 2]], "output": {"Alt": [[2, 1]]}},
            {"index": 2, "name": "blank", "hypothesis": "nothing to move",
             "input": [[0]], "output": [[9, 9]]},
        ],
    }
    text = format_file(d)
    assert _roundtrip(d) == d
    assert '"witnesses": [{' in text
    assert "[1,2]" in text
    assert '[[0,2,0,2],"D4_LR"]' in text
    assert '"Flip": null' in text
