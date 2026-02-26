#!/usr/bin/env bash
# Install the module into the local Istari agent's modules directory.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Detect OS and set agent modules path
if [[ "$OSTYPE" == "darwin"* ]]; then
    MODULES_DIR="$HOME/Library/Application Support/istari_agent/istari_modules/vibekanban"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    MODULES_DIR="/opt/local/istari_agent/istari_modules/vibekanban"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

echo "Installing to: $MODULES_DIR"
mkdir -p "$MODULES_DIR"

# Copy module files
rsync -av --delete \
    "$ROOT_DIR/src/" \
    "$ROOT_DIR/function_schemas/" \
    "$ROOT_DIR/module_manifest.json" \
    "$MODULES_DIR/"

echo "Done. Restart the Istari agent to pick up changes."
