#!/usr/bin/env bash
set -euo pipefail

script_path="$(readlink -f "${BASH_SOURCE[0]}")"
workspace="$(cd "$(dirname "$script_path")/.." && pwd)"
launcher="$workspace/scripts/run_praxys_mcp.py"
if [[ ! -f "$launcher" ]]; then
  echo "Praxys MCP launcher not found at $launcher." >&2
  exit 1
fi

cd "$workspace"
export PRAXYS_MCP_USE_CURRENT_PYTHON=1
exec python -m scripts.run_praxys_mcp local "$@"
