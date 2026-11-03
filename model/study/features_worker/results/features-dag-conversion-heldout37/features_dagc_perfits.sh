#!/bin/bash
# The fit of item 10 for one arm. Usage: features_dagc_perfits.sh ARM LEVEL [gold|drawn] [PROCS]
#   ARM    a name for the arm: rows-ARM-wN.jsonl in perrel/. Suggested: rel, comp, fam, hyb (the primary), and control (LEVEL hyb, label drawn).
#   LEVEL  rel (per relation), comp (per component), fam (per lib section or derived family), hyb (primary)
# Fit options are those of features_ps_fits.sh with no --drop: the columns that read order no longer exist and the offset is `lq` of the off walks, so its prior facts stay in.
# Fit rows: PS_FIT (default fit-cut-off). Tune rows: PS_TUNE (default test-parents-off). Rows are the names of scratch/data-NAME.npz.
D=$(cd "$(dirname "$0")" && pwd)
ARM=$1
LEVEL=$2
L=${3:-gold}
P=${4:-4}
exec bash $D/features_dagc_env.sh "$P" features_dagc_perfit.py "$ARM" --procs "$P" --eta .15 --ntok 150 --depth 4 --rounds 200 --label "$L" --level "$LEVEL" --cap 30000 --cap-min 4000 --cap-per 8 --selfkeys ${PS_SELF:-40}
