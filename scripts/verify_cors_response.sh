#!/usr/bin/env bash
# Verify one CORS preflight response using exact values and tokens.
set -euo pipefail

if (( $# < 2 )); then
  echo "usage: verify_cors_response.sh HEADERS ORIGIN [METHOD HEADER...]" >&2
  exit 2
fi

headers_file="$1"
expected_origin="$2"
shift 2

header_values() {
  local wanted="$1"
  awk -v wanted="${wanted}" '
    {
      line = $0
      sub(/\r$/, "", line)
      separator = index(line, ":")
      if (separator == 0) next
      name = substr(line, 1, separator - 1)
      value = substr(line, separator + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      if (tolower(name) == tolower(wanted)) {
        print value
      }
    }
  ' "${headers_file}"
}

token_present() {
  local value="$1" wanted="$2"
  awk -v value="${value}" -v wanted="${wanted}" '
    BEGIN {
      count = split(value, tokens, ",")
      for (i = 1; i <= count; i++) {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", tokens[i])
        if (tolower(tokens[i]) == tolower(wanted)) exit 0
      }
      exit 1
    }
  '
}

mapfile -t allowed_origins < <(
  header_values access-control-allow-origin
)
(( ${#allowed_origins[@]} == 1 ))
test "${allowed_origins[0]}" = "${expected_origin}"

if (( $# == 0 )); then
  exit 0
fi

expected_method="$1"
shift
allowed_methods="$(
  header_values access-control-allow-methods | paste -sd, -
)"
token_present "${allowed_methods}" "${expected_method}"

allowed_headers="$(
  header_values access-control-allow-headers | paste -sd, -
)"
for expected_header in "$@"; do
  token_present "${allowed_headers}" "${expected_header}"
done
