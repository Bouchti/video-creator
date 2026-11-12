#!/bin/bash
# bundle the exporter (it compiles story.ts / cast.ts in) and export frames: export_hoover.sh <outDir> <f0> <f1>
cd "$(dirname "$0")/.."
npx esbuild scripts/export_hoover.ts --bundle --platform=node --format=esm --outfile=scripts/export_hoover.mjs --external:@napi-rs/canvas \
  --banner:js="import {createRequire} from 'module'; const require = createRequire(import.meta.url); import {createCanvas as __cc} from '@napi-rs/canvas'; globalThis.document = { createElement: () => __cc(2, 2) };" --log-level=warning
node scripts/export_hoover.mjs "$@"
