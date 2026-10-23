#!/usr/bin/env bash
# Static reverse of rspec-core 3.12.2 --bisect + fastlane .rspec (nothing executed except curl/tar/grep/sed). Run from an empty dir.
set -euo pipefail
curl -sSL -o rspec-core-3.12.2.gem https://rubygems.org/downloads/rspec-core-3.12.2.gem
curl -sSL -o fl-76eeb3f.tgz https://codeload.github.com/fastlane/fastlane/tar.gz/76eeb3f9352a657fd979ae00e89e49a388729e30
echo "## sha256"; sha256sum rspec-core-3.12.2.gem fl-76eeb3f.tgz
mkdir -p rc p; tar xf rspec-core-3.12.2.gem -C rc data.tar.gz; tar xzf rc/data.tar.gz -C rc; tar xzf fl-76eeb3f.tgz -C p --strip-components=1
L=rc/lib/rspec/core
echo "## B1 CLI: --seed = rand:SEED; --bisect[=verbose] swaps in the Bisect invocation (option_parser.rb)"; sed -n 68,75p $L/option_parser.rb | cat -n
echo "## B2 coordinator: minimize, then publish repro command; failure -> bisect_failed"; sed -n 27,45p $L/bisect/coordinator.rb
echo "## B3 minimizer: candidates = all - failed; a subset 'reproduces' iff ALL original failures fail (line 150)"; grep -n "" $L/bisect/example_minimizer.rb | sed -n '19,81p;113,165p'
echo "## B4 repro command keeps original non-location args (incl. --seed); --bisect stripped"; grep -n "" $L/bisect/shell_command.rb | sed -n '13,15p;32,41p;99,104p'
echo "## B5 runner default: fork if supported; :shell only via config.bisect_runner in a --require file"; grep -n "" $L/configuration.rb | sed -n '481,491p;518p;2098,2111p'
echo "## B6 fork runner: parent boots once (incl. --require files), each subset runs in a fork that load_spec_files"; grep -n "" $L/bisect/fork_runner.rb | sed -n '51,66p;80,115p'
echo "## B7 random order is per-sibling sort_by jenkins(seed+id) (filter independent)"; sed -n 25,30p $L/ordering.rb
echo "## B8 fastlane .rspec at 76eeb3f (spec_helper is a --require, so fork runner loads it once)"; cat p/.rspec
echo "## B9 lockfile pin"; grep -n "^    rspec-core (" p/Gemfile.lock
