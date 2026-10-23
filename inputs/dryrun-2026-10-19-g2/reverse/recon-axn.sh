#!/usr/bin/env bash
# Static reverse for G2 (teamshares/axn#235). Nothing from axn is executed: curl, tar, sha256sum, grep, sed, diff only. Run in an empty dir.
set -euo pipefail
B=8daba1dcb4e1f44e2a26c87e2d602c10fc04eca9; M=6c62d568e27844bf7500be0a54425b7c9c65a8cc
curl -sSL -o base.tgz  https://codeload.github.com/teamshares/axn/tar.gz/$B
curl -sSL -o merge.tgz https://codeload.github.com/teamshares/axn/tar.gz/$M
curl -sSL -o rspec-core-3.12.2.gem https://rubygems.org/downloads/rspec-core-3.12.2.gem
curl -sSL -o rspec-core-3.13.2.gem https://rubygems.org/downloads/rspec-core-3.13.2.gem
echo "## sha256"; sha256sum base.tgz merge.tgz rspec-core-3.12.2.gem rspec-core-3.13.2.gem
mkdir -p b m r12 r13; tar xzf base.tgz -C b --strip-components=1; tar xzf merge.tgz -C m --strip-components=1
for v in 12 13; do tar xf rspec-core-3.$v.2.gem -C r$v data.tar.gz; tar xzf r$v/data.tar.gz -C r$v; done
echo "## A1 merge tree = base + PR: files differing (expect the 9 spec files only)"; diff -rq b m || true
echo "## A2 lockfile pins"; grep -nE "^    rspec-core \(|^    rspec-mocks \(|^   [0-9]+\.[0-9]+\.[0-9]+$" b/Gemfile.lock; sed -n '/^BUNDLED WITH/,+1p' b/Gemfile.lock
echo "## A3 CI ruby matrix + spec command (main.yml); Rakefile :spec is RSpec::Core::RakeTask (no --order)"; sed -n 13,30p b/.github/workflows/main.yml; sed -n 4,6p b/Rakefile
echo "## A4 .rspec (no --order/--seed => defined order in CI)"; cat b/.rspec; echo "grep order|seed|random spec_helper:"; grep -nE "order|seed|random" b/spec/spec_helper.rb || echo "(none)"
echo "## A5 spec_helper global before: Testing.reset! + reset_adapters! (does not reset @on_exception, registries, consts)"; sed -n 36,42p b/spec/spec_helper.rb; sed -n 43,49p b/lib/axn/testing.rb
echo "## M1 registry duplicate raise + :custom writers in shared examples; .clear! example registers without clearing (base)"; sed -n 34,41p b/lib/axn/internal/registry.rb; grep -n "register(:custom\|clear!\|it \"" b/spec/support/shared_examples/registry_behavior.rb; grep -n "it_behaves_like \"a registry\"\|RSpec.describe" b/spec/axn/strategies_spec.rb b/spec/axn/async/registry_spec.rb; sed -n 35,38p b/spec/axn/strategies_spec.rb; grep -n "duplicate_error_class =" b/lib/axn/strategies.rb b/lib/axn/async/adapters.rb
echo "## M2 ErrorHandlerMiddleware defined lazily (client.rb) and referenced by constant in client_spec (base)"; sed -n 108,112p b/lib/axn/extras/strategies/client.rb; grep -n "ErrorHandlerMiddleware" b/spec/axn/extras/strategies/client_spec.rb
echo "## M3 real-require fixtures in tools/registry_spec + exact-membership assertions"; grep -n "fixture_dir) {\|ensure_loaded\|remove_const" b/spec/axn/tools/registry_spec.rb; grep -n "contain_exactly\|).to eq(\[" b/spec/axn/tools/registry_spec.rb
echo "## M4 lazy let original_handler restore (5 files)"; grep -rn "let(:original_handler)\|let(:original) " b/spec
echo "## B10 rspec-core --bisect unchanged 3.12.2 -> 3.13.2? (diff of bisect/ + example_minimizer)"; diff -r r12/lib/rspec/core/bisect r13/lib/rspec/core/bisect && echo "bisect/ IDENTICAL"
echo "## B11 3.13.2 minimizer reproduce rule (enablers cannot be found: a subset counts only if the original failures FAIL)"; grep -n "failed_example_ids & results.failed_example_ids\|def bisect_over\|lhs, rhs" r13/lib/rspec/core/bisect/example_minimizer.rb
echo "## B12 3.13.2 option_parser --bisect / --seed"; grep -n "'--bisect\|'--seed\|'--order" r13/lib/rspec/core/option_parser.rb
echo "## B13 PR diff (spec only)"; diff -ru b/spec m/spec | grep -E "^(\+\+\+|@@)" || true
