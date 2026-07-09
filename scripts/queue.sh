#!/usr/bin/env bash
# Wrapper for queue.ts; see there for details.
exec bun "${0%.sh}.ts" "$@"
