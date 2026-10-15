#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:$PWD/src"
python3 -m muse_mem.cli run \
  --config configs/example.json \
  --input examples/example.json \
  --output runs/example/output.json
python3 -m muse_mem.cli inspect \
  --config configs/example.json \
  --namespace example
