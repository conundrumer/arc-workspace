#!/bin/bash
# usage: gold_dag_env.sh ARG... : runs the Mac runtime python (runtime-ba0754492) in this folder, with the priors and the pinned sampler code of the combined kit. ORCUT_KEPT_NODES defaults to 48.
HERE=$(cd "$(dirname "$0")" && pwd)
HERE_CODE=$HERE exec bash "$HERE/../combined-kit/gold_combined_env.sh" "$@"
