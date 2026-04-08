#!/bin/bash
set -e  # stop on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Pulling PeleLMeX..."
git pull origin development

echo "Syncing submodules..."
git submodule update --init --recursive

echo "Re-attaching PelePhysics to qss-benchmark..."
cd Submodules/PelePhysics
git checkout qss-benchmark

echo "Done. All synced."
