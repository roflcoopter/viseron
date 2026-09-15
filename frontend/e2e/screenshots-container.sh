#!/usr/bin/env bash
# Runs the screenshot suite inside the container created by screenshots.sh.

set -euo pipefail

# Install on the first run and store hash for cache control
lock_hash="$(sha256sum package-lock.json | cut -d " " -f 1)"
if [ "$(cat node_modules/.viseron-lock-hash 2>/dev/null || true)" != "$lock_hash" ]; then
  echo "Installing frontend dependencies"
  npm ci
  echo "$lock_hash" >node_modules/.viseron-lock-hash
fi

npm run e2e:screenshots:run -- "$@"
