#!/usr/bin/env bash
# Static reverse for F6 (nothing from fastlane is executed). Run from an empty dir; needs curl, tar, sha256sum, grep, sed, diff.
set -euo pipefail
P=76eeb3f9352a657fd979ae00e89e49a388729e30; F=148c1c9b4c041b1659ea633f2632dd47eef8cb04
for c in $P $F; do curl -sSL -o fl-${c:0:7}.tgz https://codeload.github.com/fastlane/fastlane/tar.gz/$c; done
curl -sSL -o rspec-core-3.12.2.gem https://rubygems.org/downloads/rspec-core-3.12.2.gem
echo "## sha256"; sha256sum fl-76eeb3f.tgz fl-148c1c9.tgz rspec-core-3.12.2.gem
mkdir -p p f rc; tar xzf fl-76eeb3f.tgz -C p --strip-components=1; tar xzf fl-148c1c9.tgz -C f --strip-components=1
tar xf rspec-core-3.12.2.gem -C rc data.tar.gz; tar xzf rc/data.tar.gz -C rc
echo "## lockfile rspec pins @76eeb3f"; grep -n "^    rspec-core (\|^    rspec-mocks (" p/Gemfile.lock
echo "## files changed 76eeb3f..148c1c9 (whole tree)"; { diff -rq p f || true; } | sort
echo "## M1 webhook after-hook (polluter, unchanged by fix)"; grep -n "after do" -A 2 p/spaceship/spec/connect_api/models/webhook_spec.rb; diff -q p/spaceship/spec/connect_api/models/webhook_spec.rb f/spaceship/spec/connect_api/models/webhook_spec.rb && echo "webhook_spec SAME"
echo "## M2 token= builds a bare client; client returns a stale @client first"; sed -n 19,35p p/spaceship/lib/spaceship/connect_api/spaceship.rb
echo "## M3 Client.new(token: nil) wires no test_flight/tunes client"; sed -n 75,100p p/spaceship/lib/spaceship/connect_api/client.rb; sed -n 168,190p p/spaceship/lib/spaceship/connect_api/client.rb
echo "## M4 raise site"; sed -n 14,18p p/spaceship/lib/spaceship/connect_api/testflight/testflight.rb; grep -n "instantiate this module with tunes_request_client" p/spaceship/lib/spaceship/connect_api/tunes/tunes.rb
echo "## M5 portal-only logins (polluters for :252 and :380)"; grep -rn "ConnectAPI.login(username, password, use_portal: true, use_tunes: false)" p/spaceship/spec | sort
echo "## M6 every spec writer of ConnectAPI @client"; grep -rln "ConnectAPI.token = \|ConnectAPI.client = \|ConnectAPI.login\|ConnectAPI.auth" p/spaceship/spec | sort; echo "lib writers:"; grep -rn "ConnectAPI.client\s*=\|ConnectAPI.token\s*=" p/spaceship/lib || echo none
echo "## M7 victims use the shared login only"; for s in build_beta_detail beta_build_metric app_store_version_release_request build_delivery; do sed -n 1,2p p/spaceship/spec/connect_api/models/${s}_spec.rb; done
echo "## M8 the fix: shared example clears ConnectAPI.client and logs into Portal"; { diff -u p/spaceship/spec/spec_helper.rb f/spaceship/spec/spec_helper.rb || true; } | sed -n '/shared_examples/,$p'
echo "## M9 lib unchanged"; diff -rq p/spaceship/lib f/spaceship/lib && echo "spaceship/lib SAME"
echo "## N1 control: ENV leak inside two_step spec, unchanged by fix"; grep -n "SPACESHIP_ONLY_ALLOW_INTERACTIVE_2FA\|it '\|context '" p/spaceship/spec/two_step_or_factor_client_spec.rb | sed -n '/when running non-interactive/,/when SPACESHIP_2FA/p'; grep -n "can only be performed" p/spaceship/lib/spaceship/two_step_or_factor_client.rb; diff -q p/spaceship/spec/two_step_or_factor_client_spec.rb f/spaceship/spec/two_step_or_factor_client_spec.rb && echo "two_step spec SAME"
echo "## R1 rspec-core 3.12.2: explicit files keep CLI order; only directories are sorted"; grep -n "def get_files_to_run" -A 5 rc/lib/rspec/core/configuration.rb; grep -n "def get_matching_files" -A 3 rc/lib/rspec/core/configuration.rb
echo "## R2 random order = sort by jenkins(seed + id) per sibling set (filter-independent)"; sed -n 25,30p rc/lib/rspec/core/ordering.rb; grep -n "ordering_strategy.order" rc/lib/rspec/core/example_group.rb rc/lib/rspec/core/world.rb
