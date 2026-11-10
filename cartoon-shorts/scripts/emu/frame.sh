#!/bin/sh
cd "$(dirname "$0")/../.." && npx esbuild scripts/emu/frame_entry.ts --bundle --platform=node --outfile=scripts/emu/frame.cjs --log-level=error && node scripts/emu/frame.cjs "$@"
