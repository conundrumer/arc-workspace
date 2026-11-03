#!/bin/bash
# Copies a pod run's light files to a local folder. pull.sh ENV_FILE REMOTE_OUT LOCAL_DIR
L=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/39487d30-036f-4e4b-ad99-183af6a33661/scratchpad/lanes
. "$1"
mkdir -p "$3"
rsync -az --timeout=25 --include='*/' --include='*.events.jsonl' --include='*.done.json' --exclude='*' \
  -e "ssh -i $L/key_sampler -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o BatchMode=yes -p $PORT" "root@$HOST:$2/" "$3/"
