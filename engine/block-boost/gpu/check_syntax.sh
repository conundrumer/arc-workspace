#!/bin/bash
# Checks gpu/bbgpu.cu for C++ errors where there is no CUDA toolchain: each kernel launch `k<<<grid, block>>>(args)` is rewritten as the call `k(args)`, and the
# CUDA headers are the declarations in gpu/stubs. It compiles nothing for a card, so it finds errors of syntax and of types, and none that the card or nvcc alone finds.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
sed -E 's/<<<.*>>>//' "$here/bbgpu.cu" > "$work/check.cpp"
g++ -std=c++17 -fsyntax-only -Wall -Wno-unused-function -I "$here/stubs" "$work/check.cpp"
echo "gpu/bbgpu.cu: no errors against the stubs"
