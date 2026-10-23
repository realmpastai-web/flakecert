#!/bin/bash
# Detached G3 resume. Caller redirects this process and must not wait on it.
# --resume skips a BOUNDED_CLEAN certificate after its sha256 matches, continues
# the unfinished seed, then the excluded set, the reverse-order path, and the
# paths that have not started. Per-seed limit is max(300, ceil(3 * arm-G seconds)).
# Wall clock is a fresh 4 h from resume_started_at. Stop after 2 environment
# setup failures (SPEC-G3.1).
set -u
cd "$(dirname "$0")/.."
echo "RESUME launcher $(date -u +%Y-%m-%dT%H:%M:%SZ)"
export PYTHONUNBUFFERED=1
exec python3 -m tools.certify_rspec.pipeline_g3 \
  --input-dir inputs/dryrun-2026-10-19-g3 \
  --gitlab-dir /var/tmp/g3-work/gitlab \
  --evidence-dir evidence/certify-rspec-g3 \
  --container g3runner \
  --postgres g3pg \
  --workers 2 \
  --setup-log /var/tmp/g3-work/prepare-db2.log \
  --resume
