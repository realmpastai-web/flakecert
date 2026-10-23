#!/bin/bash
set -uo pipefail
set +e
docker exec -w /gitlab -e CI=true -e RSPEC_ORDER=defined -e G3_DB_SUFFIX= -e MALLOC_ARENA_MAX=2 g3runner bash -lc 'cd /gitlab && bin/rspec --format documentation spec/services/timelogs/delete_service_spec.rb'
rc=$?
set -e
test "$rc" -eq 0
echo REPLAY_OK
