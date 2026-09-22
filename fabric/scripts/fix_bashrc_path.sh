#!/usr/bin/env bash
set -euo pipefail

BASHRC="/home/korchien/.bashrc"
# Remove any previous fabric-samples PATH lines (good or broken)
sed -i '/fabric-samples\/bin/d' "$BASHRC"
# Add correct Linux PATH entry
echo 'export PATH=$HOME/fabric-samples/bin:$PATH' >> "$BASHRC"
chown korchien:korchien "$BASHRC"
echo "Updated $BASHRC:"
tail -5 "$BASHRC"
