#!/bin/sh
# replay.sh for cause-9.json
set -eu
cd /workspace/hark-tasks/flakecert-g2-2-1019
export PYTHONPATH=/workspace/hark-tasks/flakecert-g2-2-1019
exec python3 -m tools.certify_rspec.replay --cert /workspace/hark-tasks/flakecert-g2-2-1019/evidence/certify-rspec-g2-2/cause-9.json
