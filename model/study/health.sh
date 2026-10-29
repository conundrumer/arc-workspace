#!/opt/homebrew/bin/bash
# Emits one line per new anomaly in the study pipeline; quiet otherwise. Checks every 30 s.
code_dir=$(cd -- "$(dirname -- "$0")" && pwd)
S=$(python3 "$code_dir/study_paths.py")
D=$S/codex-adm
declare -A seen state lastev
hist=()
say() { local key=$1; shift; if [ -z "${seen[$key]:-}" ]; then echo "$*"; seen[$key]=1; fi; }
clear_key() { unset "seen[$1]"; }
age() { [ -e "$1" ] && echo $(( $(date +%s) - $(stat -f %m "$1") )) || echo -1; }
while read -r tid st; do state[$tid]=$st; lastev[$tid]=$(date +%s); done < <(jq -r 'select(.method=="thread/status/changed") | "\(.params.threadId) \(.params.status.type)"' $D/out.ndjson)
L0=$(wc -l < $D/out.ndjson)
while true; do
  # Logs that should keep moving while their process runs.
  for spec in "corpus-v12|$S/ast/run/corpus-v12-body-full.log|run/corpus.py.*corpus-v12-body-full" "pool-follower|$S/judge2/pool-ast-v4/follow.log|follow_corpora.py" "kept-streams|$S/ast/run/kept-streams-v12-body-full-5ee2f066.log|check_kept_streams.py"; do
    IFS='|' read -r name log pat <<< "$spec"
    if pgrep -f "$pat" >/dev/null; then
      a=$(age "$log")
      if [ "$a" -gt 300 ]; then say "stall-$name" "STALL $name: no log line for ${a}s ($log)"; else clear_key "stall-$name"; fi
      if grep -qE 'Traceback|^[A-Za-z]*Error|Killed|MemoryError' <(tail -5 "$log" 2>/dev/null); then say "err-$name-$(tail -1 "$log" | cksum)" "ERROR $name: $(tail -1 "$log" | cut -c1-200)"; fi
    fi
  done
  # Memory: any scratchpad python over 8 GB footprint.
  for pid in $(pgrep -f "$S/.*python|venv.*/bin/python"); do
    f=$(vmmap --summary $pid 2>/dev/null | awk '/^Physical footprint:/{print $3}')
    case "$f" in *G) if [ "$(echo "${f%G} > 8" | bc)" = 1 ]; then say "mem-$pid" "MEMORY pid $pid footprint $f: $(ps -o args= -p $pid | cut -c1-120)"; fi;; esac
  done
  # Disk: absolute floor, and projected time to full from the last 10 minutes.
  free=$(df -m "$S" | awk 'NR==2{print $4}')
  hist+=("$(date +%s):$free"); [ ${#hist[@]} -gt 21 ] && hist=("${hist[@]:1}")
  if [ "$free" -lt 30000 ]; then say "disk-floor" "DISK only $((free/1024)) GB free on the scratchpad volume"; else clear_key disk-floor; fi
  if [ ${#hist[@]} -ge 21 ]; then
    t0=${hist[0]%%:*}; f0=${hist[0]##*:}; dt=$(( $(date +%s) - t0 )); df_=$(( f0 - free ))
    if [ "$df_" -gt 0 ]; then left=$(( free * dt / df_ )); if [ "$left" -lt 7200 ]; then say "disk-rate-$((free/10240))" "DISK filling: $((free/1024)) GB free, down $((df_/1024)) GB in $((dt/60)) min, full in about $((left/60)) min"; fi; fi
  fi
  # Codex app-server: alive, server requests nobody answers, threads active but silent.
  pgrep -f 'codex app-server' >/dev/null || say "codex-dead" "CODEX app-server is not running"
  now=$(date +%s)
  while read -r kind tid rest; do
    case $kind in
      REQ) echo "REQUEST from codex server: $rest thread=$tid";;
      ST) state[$tid]=$rest; lastev[$tid]=$now;;
      EV) lastev[$tid]=$now;;
    esac
  done < <(tail -n +$((L0+1)) $D/out.ndjson | jq -rc 'if (.method != null and .id != null) then "REQ \(.params.threadId // "-") \(.method) id=\(.id)" elif .method=="thread/status/changed" then "ST \(.params.threadId) \(.params.status.type)" elif .params.threadId then "EV \(.params.threadId) -" else empty end' 2>/dev/null)
  L0=$(wc -l < $D/out.ndjson)
  for n in $(cat $D/owners.txt); do
    t=$(cat $D/$n.thread)
    if [ "${state[$t]:-}" = active ] && [ $(( now - ${lastev[$t]:-$now} )) -ge 900 ]; then say "silent-$n-${lastev[$t]}" "SILENT codex thread $n: active with no events for 15 min"; fi
  done
  # Codex first-pass judge output.
  if [ -s $S/judge2/codex-audit.jsonl ]; then
    bad=$(jq -c 'select((.pair_id and .render_version and (.issues|type=="array"))|not)' $S/judge2/codex-audit.jsonl 2>&1 | head -1)
    [ -n "$bad" ] && say "cpass-bad-$(echo "$bad" | cksum)" "CODEX AUDIT malformed line: ${bad:0:200}"
  fi
  sleep 30
done
