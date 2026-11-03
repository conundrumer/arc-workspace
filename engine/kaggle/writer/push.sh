#!/bin/bash
# push.sh BUNDLE MESSAGE: uploads BUNDLE/dataset as a new version of the dataset, waits until it is ready, then pushes BUNDLE/kernel. Prints the kernel version.
set -u
B=$1; MSG=$2
kaggle datasets version -p $B/dataset -m "$MSG" 2>&1 | tail -3
for i in $(seq 1 60); do s=$(kaggle datasets status conundrumer/arc-synth-bundle 2>&1 | tail -1); echo "$(date +%T) dataset $s"; [ "$s" = ready ] && break; sleep 10; done
kaggle kernels push -p $B/kernel 2>&1 | tail -3
