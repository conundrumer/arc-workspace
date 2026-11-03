#!/bin/bash
# submit.sh VERSION MESSAGE: submits that version of the kernel to the competition, and lists the submissions.
set -u
kaggle competitions submit arc-prize-2026-arc-agi-2 -k conundrumer/arc-synth-run -v $1 -f submission.json -m "$2" 2>&1 | tail -3
kaggle competitions submissions arc-prize-2026-arc-agi-2 2>&1 | head -5
