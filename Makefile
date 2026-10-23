PYTHON ?= python3.11
export PYTHONPATH := $(CURDIR)
export PYTHONHASHSEED := 0
export PYTHONUNBUFFERED := 1

.PHONY: unit freeze envs baseline flakecert comparator ledger verify audit audit-csv audit-csv-real all ingest rspec-sample rspec-attempt-to-fix pytest-attempt-to-fix queuetrail-test queuetrail-rails-test fetch-inputs atf20-gates

unit:
	$(PYTHON) -m unittest tests.test_unit tests.test_ingest tests.test_verdict_audit

freeze:
	$(PYTHON) tools/freeze.py

envs: freeze
	$(PYTHON) tools/envs.py

baseline:
	$(PYTHON) tools/baseline.py

flakecert:
	$(PYTHON) tools/flakecert_search.py

comparator:
	$(PYTHON) tools/comparator.py

ledger:
	$(PYTHON) tools/ledger.py

# REPLAY_SKIP=1 skips live certificate replay and records pass null.
# Plain `make verify` replays every certificate and is what records the
# committed online report (resolve preflight included).
# OFFLINE=1 skips that preflight. If the committed report is an online
# match, the offline run writes evidence/offline/ and does not replace
# evidence/verify-report.json, evidence/verify.log, or evidence/SHA256SUMS.
verify:
	$(PYTHON) tools/verify.py $(if $(OFFLINE),--offline,) $(if $(REPLAY_SKIP),--replay-skip,)

# Nominate candidates from the frozen JUnit and collector samples.
# SHA= sets --sha. Without it, CI variables or git rev-parse supply the sha.
INGEST_REPORTS := $(wildcard docs/inputs/flakecert-ingest/samples/pytest-junit-*.xml) \
	$(wildcard docs/inputs/flakecert-ingest/samples/jest-junit-*.xml) \
	$(wildcard docs/inputs/flakecert-ingest/samples/gotestsum-junit-*.xml) \
	$(wildcard docs/inputs/flakecert-ingest/samples/buildkite-collector-*.json)

ingest:
	mkdir -p ingest
	$(PYTHON) tools/ingest.py --out ingest/candidates.json $(if $(SHA),--sha $(SHA),) $(if $(REPO_ROOT),--repo-root $(REPO_ROOT),) $(INGEST_REPORTS)

audit:
	$(PYTHON) tools/audit_verdicts.py --in inputs/flakecert-verdict-audit/sample/dd-test-run.json --out audit/verdicts.json

audit-csv:
	$(PYTHON) tools/audit_verdicts.py --in inputs/flakecert-csv-sample/sample/pup-export.csv --out audit/verdicts-csv.json

audit-csv-real:
	$(PYTHON) tools/audit_verdicts.py --in inputs/flakecert-csv-sample/sample/real-cassette-search.csv --out audit/verdicts-csv-real.json

all: freeze envs baseline flakecert comparator ledger verify

rspec-sample:
	$(PYTHON) -m flakecert.runners.rspec

rspec-attempt-to-fix:
	$(PYTHON) -m flakecert.runners.rspec_attempt_to_fix

pytest-attempt-to-fix:
	$(PYTHON) -m flakecert.runners.pytest_attempt_to_fix

# Static QueueTrail checks only. Does not run make verify and does not load test-queue.
queuetrail-test:
	nice -n 19 ruby tools/queuetrail/test/hook_test.rb
	nice -n 19 python3 -m pytest tests/test_queuetrail.py -q
	nice -n 19 python3 tools/queuetrail/reverse_check.py --gem inputs/rea-brief-test-queue/test-queue-0.12.0.gem --control inputs/rea-brief-test-queue/parallel_tests-5.8.0.gem --expect inputs/rea-brief-test-queue/observations.json

# Download the pinned datadog-ci gem when it is missing. A matching local file
# skips the network. Does not install or run datadog-ci.
fetch-inputs:
	bash scripts/fetch-inputs.sh

# Policy-model gates. Does not run fastlane and does not install datadog-ci.
# fetch-inputs runs first so sha256sum -c can see the pinned gem bytes.
atf20-gates: fetch-inputs
	mkdir -p /tmp/atf20-rspec-gems
	echo "155b54480f28e2b2813185077fe435c2d663031616360ed3b179a9d6a55d2551  inputs/rspec-pins/rspec-core-3.12.2.gem" | sha256sum -c -
	cd inputs/rspec-pins && sha256sum -c SHA256SUMS
	gem install --local --no-document --install-dir /tmp/atf20-rspec-gems inputs/rspec-pins/rspec-support-3.12.1.gem
	gem install --local --no-document --ignore-dependencies --install-dir /tmp/atf20-rspec-gems inputs/rspec-pins/rspec-core-3.12.2.gem
	GEM_HOME=/tmp/atf20-rspec-gems GEM_PATH=/tmp/atf20-rspec-gems $(PYTHON) -m unittest tests.test_atf20 -v

# Static QueueTrail-Rails checks only. Does not install or run Rails.
queuetrail-rails-test:
	nice -n 19 ruby tools/queuetrail/test/rails_hook_test.rb
	nice -n 19 python3 -m pytest tests/test_queuetrail_rails.py tests/test_queuetrail.py -q
	nice -n 19 python3 tools/queuetrail/reverse_check_rails.py --gem inputs/rea-brief-rails-parallel/activesupport-8.1.4.gem --expect inputs/rea-brief-rails-parallel/observations.json
	cd inputs/rea-brief-rails-parallel && nice -n 19 sha256sum -c SHA256SUMS
