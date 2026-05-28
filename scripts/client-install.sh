#!/usr/bin/env bash
set -euo pipefail

GATEWAY_URL=""
TOKEN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gateway-url)
      GATEWAY_URL="$2"
      shift 2
      ;;
    --token)
      TOKEN="$2"
      shift 2
      ;;
    -h|--help)
      cat <<EOF
Usage: bash scripts/client-install.sh --gateway-url URL [--token TOKEN]

Installs only the OpenCLI client plugin for an existing Parquet Query Gateway.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$GATEWAY_URL" ]]; then
  echo "--gateway-url is required" >&2
  exit 2
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to install OpenCLI" >&2
  exit 1
fi

if ! command -v opencli >/dev/null 2>&1; then
  npm install -g @jackwener/opencli
fi

opencli plugin install "file://$PWD" || opencli plugin update parquet

cat <<EOF

Client installation complete.

Set these in your shell:
  export PARQUET_GATEWAY_URL="$GATEWAY_URL"
EOF

if [[ -n "$TOKEN" ]]; then
  cat <<EOF
  export PARQUET_GATEWAY_TOKEN="$TOKEN"
EOF
else
  cat <<EOF
  # No token was provided. The first authenticated command will open Feishu login.
  # You can also run: opencli parquet login
EOF
fi

cat <<EOF

Verify:
  opencli parquet smoke-test
  opencli parquet datasets
EOF
