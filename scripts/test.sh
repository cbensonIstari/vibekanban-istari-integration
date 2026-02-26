#!/usr/bin/env bash
# Run the test suite for vibekanban-istari-integration.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Running unit tests ==="
python3 -m pytest "$ROOT_DIR/tests/" -v

echo ""
echo "=== All tests passed ==="
