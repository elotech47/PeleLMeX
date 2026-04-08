#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Pulling PeleLMeX..."
git pull origin development

echo "Syncing submodules..."
git submodule update --init --recursive

echo "Re-attaching PelePhysics to qss-benchmark..."
cd Submodules/PelePhysics
git remote set-url origin https://github.com/elotech47/PelePhysics.git
git fetch origin '+refs/heads/*:refs/remotes/origin/*'
git checkout qss-benchmark 2>/dev/null || git checkout -b qss-benchmark origin/qss-benchmark

cd "$SCRIPT_DIR"
echo "Done. All synced."
