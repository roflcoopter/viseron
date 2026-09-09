#!/usr/bin/env bash
# Regenerates the documentation screenshots inside the pinned Playwright image.
#
# Runs a container to have a consistent environment between development
# environemnts and CI runners.

set -euo pipefail

e2e_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$e2e_dir/../.." && pwd)"

if ! docker info >/dev/null 2>&1; then
  cat >&2 <<'EOF'
error: cannot reach a Docker daemon.

Docker is required to generate the screenshots.
EOF
  exit 1
fi

image="$(node "$e2e_dir/playwright-image.mjs")"

docker_flags=(
  # Chromium needs a real /dev/shm or it crashes on large pages.
  --ipc=host
  --init
  # Deps are stored in a named volume for caching purposes
  --mount "type=volume,src=viseron-screenshots-node-modules,dst=/work/frontend/node_modules,volume-nocopy"
  --workdir /work/frontend
  # playwright.config.ts only compares when CI=true, so unset it here
  --env CI=
)
[ -t 1 ] && docker_flags+=(--tty)

echo "Generating screenshots in $image"

# Create the container
container="$(docker create "${docker_flags[@]}" "$image" \
  bash e2e/screenshots-container.sh "$@")"
trap 'docker rm --force "$container" >/dev/null' EXIT

# Copy code into the container to avoid bind mounting
tar -C "$repo_root" -cf - \
  --exclude=frontend/node_modules --exclude=frontend/test-results \
  --exclude=frontend/dist --exclude=frontend/coverage \
  frontend docs/static/img/ui |
  docker cp - "$container:/work"

# Start the container to generate the screenshot
status=0
docker start --attach "$container" || status=$?

# Copy any newly generated screenshot from inside the container
docker cp "$container:/work/docs/static/img/ui/." "$repo_root/docs/static/img/ui/"
rm -rf "$repo_root/frontend/test-results"
docker cp "$container:/work/frontend/test-results" "$repo_root/frontend/" 2>/dev/null || true

exit $status
