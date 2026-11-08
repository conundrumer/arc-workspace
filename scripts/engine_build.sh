#!/bin/bash
# engine_build.sh SHA NAME [PART...]: an engine build of commit SHA under the name NAME, made in one persistent build checkout and one shared cargo target folder, so that cargo recompiles only the crates whose files differ from the last build's commit. One build runs at a time.
#
# The build root is $ENGINE_BUILD_ROOT, or work/engine-builds in the main checkout of the repo. It holds:
#   checkout/      the build checkout, a detached worktree of the repo. Each build moves it to SHA, so git rewrites only the files that differ.
#   target/        the cargo target folder. Only the build checkout builds into it, so cargo never reuses a crate built from another tree.
#   builds/NAME/   the engine build: the arclog and arclog_features packages, for PYTHONPATH.
#   linux/NAME/    Linux x86_64 wheels of arclog and arclog_features and the feature-encoder binary, with SHA256SUMS and COMMIT, for a pod.
#   zig/           the C compiler wrappers that link the Linux binaries with zig, through maturin's `zig cc`.
#   bin/           tool binaries, each as TOOL-NAME.
#   logs/NAME.log  each step's time and cargo's output.
#   build.lock     held while a build step runs.
#
# PARTs, in any order (default: wheel):
#   wheel    arclog and arclog_features into builds/NAME/.
#   encoder  feature-encoder into bin/feature-encoder-NAME.
#   cli      arclog-cli's arclog-cli, verdicts and stream_round_trip into bin/.
#   linux    Linux x86_64 wheels and feature-encoder, cross-built with zig for glibc 2.17 into the same target folder, into linux/NAME/.
#   linux-encoder  the Linux feature-encoder alone, added to the wheels already in linux/NAME/.
#   tests    the tests of the arclog crate.
#
# A step that fails prints the end of its cargo output and ends the build with status 1.
# Run it through scripts/run_heavy.py, as any build.
set -u
SHA=$1; NAME=$2; shift 2
PARTS=${*:-wheel}
MAIN=$(dirname "$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir)")
R=${ENGINE_BUILD_ROOT:-$MAIN/work/engine-builds}
B=$R/checkout; T=$R/target; LOG=$R/logs/$NAME.log; LOCK=$R/build.lock
mkdir -p "$R/builds" "$R/bin" "$R/logs" "$R/wheels" "$R/linux"
: > "$LOG"
step() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }

# Runs its arguments in the build checkout at SHA, while holding the lock.
locked() {
  until mkdir "$LOCK" 2>/dev/null; do sleep 1; done
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT
  [ -d "$B" ] || git -C "$MAIN" worktree add --detach "$B" "$SHA" > /dev/null 2>&1
  git -C "$B" checkout -q --detach --force "$SHA" && git -C "$B" clean -fdq && "$@" >> "$LOG" 2>&1
  local status=$?
  rmdir "$LOCK" 2>/dev/null; trap - EXIT
  return $status
}

fail() { step "$1 failed"; grep -E "^error" -A8 "$LOG" | head -40; exit 1; }

wheel() {
  rm -rf "$R/wheels/$NAME" && mkdir -p "$R/wheels/$NAME" &&
  CARGO_TARGET_DIR=$T PYTHONDONTWRITEBYTECODE=1 maturin build --offline --profile tool --manifest-path "$B/engine/arclog-py/Cargo.toml" -o "$R/wheels/$NAME" &&
  CARGO_TARGET_DIR=$T PYTHONDONTWRITEBYTECODE=1 maturin build --offline --profile tool --manifest-path "$B/engine/arclog-features-py/Cargo.toml" -o "$R/wheels/$NAME"
}

encoder() {
  CARGO_TARGET_DIR=$T cargo build --offline --profile tool --manifest-path "$B/engine/Cargo.toml" -p arclog-encoder --bin feature-encoder &&
  cp "$T/tool/feature-encoder" "$R/bin/feature-encoder-$NAME"
}

cli() {
  CARGO_TARGET_DIR=$T cargo build --offline --profile tool --manifest-path "$B/engine/Cargo.toml" -p arclog-cli --bin arclog-cli --bin verdicts --bin stream_round_trip &&
  for TOOL in arclog-cli verdicts stream_round_trip; do cp "$T/tool/$TOOL" "$R/bin/$TOOL-$NAME"; done
}

linux() {
  rm -rf "$R/linux/$NAME" && mkdir -p "$R/linux/$NAME" &&
  for P in arclog-py arclog-features-py; do
    CARGO_TARGET_DIR=$T PYTHONDONTWRITEBYTECODE=1 maturin build --offline --profile tool --target x86_64-unknown-linux-gnu --zig --manifest-path "$B/engine/$P/Cargo.toml" -o "$R/linux/$NAME" || return 1
  done &&
  linux_encoder
}

# The Linux feature-encoder into linux/NAME/, with zig as the linker and the C compiler, for the glibc that the wheels target; then the folder's SHA256SUMS, over every file it holds, and COMMIT. cc-rs runs the C compiler through no wrapper, since sccache refuses the zig one.
linux_encoder() {
  local Z=$R/zig M
  M=$(command -v maturin) || return 1
  mkdir -p "$Z" "$R/linux/$NAME" &&
  printf '#!/bin/sh\nexec "%s" zig cc -- -g -fno-sanitize=all -target x86_64-linux-gnu.2.17 "$@"\n' "$M" > "$Z/cc" &&
  printf '#!/bin/sh\nexec "%s" zig c++ -- -g -fno-sanitize=all -target x86_64-linux-gnu.2.17 "$@"\n' "$M" > "$Z/c++" &&
  printf '#!/bin/sh\nexec "%s" zig ar -- "$@"\n' "$M" > "$Z/ar" &&
  printf '#!/bin/sh\nexec "%s" zig ranlib -- "$@"\n' "$M" > "$Z/ranlib" &&
  chmod +x "$Z/cc" "$Z/c++" "$Z/ar" "$Z/ranlib" &&
  RUSTC_WRAPPER= CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=$Z/cc CC_x86_64_unknown_linux_gnu=$Z/cc CXX_x86_64_unknown_linux_gnu=$Z/c++ AR_x86_64_unknown_linux_gnu=$Z/ar RANLIB_x86_64_unknown_linux_gnu=$Z/ranlib \
    CARGO_TARGET_DIR=$T cargo build --offline --profile tool --target x86_64-unknown-linux-gnu --manifest-path "$B/engine/Cargo.toml" -p arclog-encoder --bin feature-encoder &&
  cp "$T/x86_64-unknown-linux-gnu/tool/feature-encoder" "$R/linux/$NAME/feature-encoder" &&
  (cd "$R/linux/$NAME" && shasum -a 256 $(ls | grep -v -x -e SHA256SUMS -e COMMIT) > SHA256SUMS && git -C "$B" rev-parse HEAD > COMMIT)
}

tests() {
  CARGO_TARGET_DIR=$T cargo test --offline -p arclog --manifest-path "$B/engine/Cargo.toml"
}

step "build $NAME of $SHA: $PARTS"
for PART in $PARTS; do
  case $PART in
    wheel)
      locked wheel || fail wheel
      rm -rf "$R/builds/$NAME" && mkdir -p "$R/builds/$NAME"
      for WHEEL in "$R/wheels/$NAME"/*.whl; do unzip -o -q "$WHEEL" -d "$R/builds/$NAME"; done
      rm -rf "$R/wheels/$NAME"
      step "engine build $R/builds/$NAME";;
    encoder) locked encoder || fail encoder; step "$R/bin/feature-encoder-$NAME";;
    cli) locked cli || fail cli; step "$R/bin/{arclog-cli,verdicts,stream_round_trip}-$NAME";;
    linux) locked linux || fail linux; step "$R/linux/$NAME";;
    linux-encoder) locked linux_encoder || fail linux-encoder; step "$R/linux/$NAME/feature-encoder";;
    tests) locked tests || fail tests; step "tests: $(grep -E '^test result' "$LOG" | awk '{p+=$4; f+=$6} END {print p" passed, "f" failed"}')";;
    *) step "unknown part $PART"; exit 1;;
  esac
done
step "done"
