#!/bin/bash
# Compress each task of a point store once its done marker appears, until no build runs. squeeze.py skips tasks it finished.
# squeeze_follow.sh STORE CACHE
store=${1:?}; cache=${2:?}
here=$(dirname "$0")
while :; do
  running=$(pgrep -f 'build_points.py' | wc -l)
  tasks=$(ls "$cache/done" | sed 's/\.json$//' | sort | comm -23 - <(sort -u "$store.squeezed"))
  [ -n "$tasks" ] && python3 -B -u "$here/squeeze.py" "$store" 0 1 $tasks
  [ "$running" -eq 0 ] && break
  /bin/sleep 60
done
echo follow done
