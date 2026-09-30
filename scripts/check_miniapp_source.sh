#!/usr/bin/env bash
# Run from miniapp/. Keep source checks identical across required and standalone CI.
set -euo pipefail

for p in login today training goal history settings science; do
  if [ ! -f "pages/$p/index.ts" ] || [ ! -f "pages/$p/index.wxml" ]; then
    echo "::error::Missing pages/$p/{index.ts,index.wxml}"
    exit 1
  fi
done
echo "All 7 page entries present."

for c in nav-bar line-chart bar-chart scatter-chart; do
  if [ ! -f "components/$c/index.ts" ] || [ ! -f "components/$c/index.wxml" ]; then
    echo "::error::Missing components/$c/{index.ts,index.wxml}"
    exit 1
  fi
done
echo "All 4 components present."

# Measure file bytes rather than allocated filesystem blocks.
# Mirror project.config.json packOptions.ignore for development-only
# metadata, and exclude generated TypeScript source that DevTools
# replaces with its compiled output.
size=$(du --apparent-size -sk \
  --exclude=node_modules \
  --exclude='package-lock.json' \
  --exclude='package.json' \
  --exclude='tsconfig.json' \
  --exclude='scripts' \
  --exclude='utils/i18n-catalog.ts' \
  . | cut -f1)
echo "miniapp/ packaged-source proxy size: ${size} KB"
if [ "$size" -gt 2000 ]; then
  echo "::error::miniapp/ source size exceeds 2 MB WeChat main-package limit"
  exit 1
elif [ "$size" -gt 1500 ]; then
  echo "::warning::miniapp/ source is ${size} KB — closing in on the 2 MB cap"
fi
