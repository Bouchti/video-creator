#!/bin/bash
# bundle the exporter and export frames: export_gimli.sh <outDir> [f0] [f1]
cd "$(dirname "$0")/.."
npx esbuild scripts/export_gimli.ts --bundle --platform=node --format=esm --outfile=scripts/export_gimli.mjs --external:@napi-rs/canvas \
  --banner:js="import {createRequire} from 'module'; const require = createRequire(import.meta.url);" --log-level=warning
node scripts/export_gimli.mjs "$@"
