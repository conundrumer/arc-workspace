#!/bin/bash
# A refit of the primary's form with no fact that reads atom order. Usage: features_ps_fits.sh ARM [gold|drawn] [PROCS]
# NOORDER is the primary's list: a form's place in gold's text, and reader counts, as gold built those. ATOMORDER is the atom's index, the pick's index, the phase under NOT, the last atom's class, and the last atom's relation.
# PRIORFACTS is each fact made from the steered weights, as the steer reads atom order. The steered prior stays as the offset.
D=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-per-relation-pool-scope-heldout37
NOORDER='readers,recency,recency_frac,kept_reads,prevform*,scopereads*'
ATOMORDER='k,ord,root2,last_derived,last_lib,last_not,last:*'
PRIORFACTS='lq,lp,steer,rank,gap_top,share_kind,entropy,top_q,der_rank'
ARM=$1
L=${2:-gold}
P=${3:-4}
exec bash $D/features_ps_env.sh "$P" features_perrel_fit.py "$ARM" --procs "$P" --eta .15 --ntok 150 --depth 4 --rounds 200 --label "$L" --level hyb --cap 30000 --cap-min 4000 --cap-per 8 --selfkeys ${PS_SELF:-40} --drop "$NOORDER,$ATOMORDER,$PRIORFACTS${PS_DROP:+,$PS_DROP}"
