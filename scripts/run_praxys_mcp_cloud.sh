#!/usr/bin/env bash
set -euo pipefail

workspace="${GITHUB_WORKSPACE:-}"
if [[ -z "$workspace" ]]; then
  echo "GITHUB_WORKSPACE is required to start praxys-local." >&2
  exit 1
fi

launcher="$workspace/scripts/run_praxys_mcp.py"
if [[ ! -f "$launcher" ]]; then
  echo "Praxys MCP launcher not found at $launcher." >&2
  exit 1
fi

cd "$workspace"
export PRAXYS_MCP_USE_CURRENT_PYTHON=1
exec python -m scripts.run_praxys_mcp local "$@"
