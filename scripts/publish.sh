#!/usr/bin/env bash
# Publish the module to the Istari registry and install locally.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Publishing module ==="
stari client publish "$ROOT_DIR/module_manifest.json"

echo ""
echo "=== Installing locally ==="
bash "$SCRIPT_DIR/install.sh"

echo ""
echo "=== Done ==="
echo "Restart the Istari agent to pick up the new version."
