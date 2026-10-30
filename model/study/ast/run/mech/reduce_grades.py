#!/usr/bin/env python3
"""Read-time reduction of evidence JSONL to transient counts; never store grades."""
import argparse
from collections import Counter
import json
from pathlib import Path
from grades import reduce_grade


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('evidence',type=Path)
    a=ap.parse_args();counts=Counter()
    with a.evidence.open() as stream:
        for line in stream:
            if line.strip():counts[reduce_grade(json.loads(line))['grade']]+=1
    print(json.dumps(dict(grade_counts=dict(counts),read_only=True),sort_keys=True))


if __name__=='__main__':main()
