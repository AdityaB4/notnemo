#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Conductor provides CONDUCTOR_ROOT_PATH pointing to the repo root.
# The .env.local there is shared across all workspaces.
ENV_SOURCE="${CONDUCTOR_ROOT_PATH:?CONDUCTOR_ROOT_PATH not set}/.env.local"

if [ ! -f "$ENV_SOURCE" ]; then
  echo "Error: $ENV_SOURCE not found. Create it first with your secrets."
  exit 1
fi

# Symlink backend/.env.local -> CONDUCTOR_ROOT_PATH/.env.local
ln -sf "$ENV_SOURCE" "$REPO_ROOT/backend/.env.local"
echo "Linked backend/.env.local -> $ENV_SOURCE"
