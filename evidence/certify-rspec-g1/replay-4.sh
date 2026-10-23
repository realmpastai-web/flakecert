#!/bin/sh
# replay.sh for cert-4.json
set -eu
cd /workspace/hark-tasks/flakecert-g1-1019
export PYTHONPATH=/workspace/hark-tasks/flakecert-g1-1019
exec python3 -m tools.certify_rspec.replay --cert /workspace/hark-tasks/flakecert-g1-1019/evidence/certify-rspec-g1/cert-4.json
