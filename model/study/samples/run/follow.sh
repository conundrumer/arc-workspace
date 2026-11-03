#!/bin/bash
# Runs chain.sh on each split again and again while the row stores and the graphs stream, so each task goes through the stages soon after its store and
# graph exist. Each stage skips current tasks. It stops after a pass that starts when no build_merged.py or rows_replay.py runs and the graph folder has not changed for 2 minutes.
#   KIT=<writer kit release folder> ARC_SAMPLE_GRAPHS=<graph folder> [POINTS=...] model/study/samples/run/follow.sh SPLIT:N [SPLIT:N ...]
set -o pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
: "${KIT:?KIT names a writer kit release}" "${ARC_SAMPLE_GRAPHS:?ARC_SAMPLE_GRAPHS names the graph folder}"
export KIT ARC_SAMPLE_GRAPHS POINTS HERE
while :; do
    quiet=0
    if ! pgrep -f 'samples/rows_replay.py|reach-kit/build_merged.py' > /dev/null && [ -z "$(find "$ARC_SAMPLE_GRAPHS" -newermt '-2 minutes' -print -quit)" ]; then quiet=1; fi
    echo "== pass $(date +%T)$([ $quiet = 1 ] && echo ', the last')"
    printf '%s\n' "$@" | xargs -P "$#" -I{} bash -c 'sn={}; "$HERE/chain.sh" "${sn%%:*}" "${sn##*:}"'  # the splits at once
    [ $quiet = 1 ] && break
    /bin/sleep 60
done
echo "== follow done $(date +%T)"
