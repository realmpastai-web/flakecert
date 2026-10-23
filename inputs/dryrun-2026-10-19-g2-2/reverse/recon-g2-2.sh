#!/usr/bin/env bash
# Static reverse for G2.2. Reads merged evidence JSON (flakecert main 611e80f) and axn base source. Executes nothing from axn.
set -euo pipefail
curl -sSL -o fc.tgz https://codeload.github.com/realmpastai-web/flakecert/tar.gz/611e80f
curl -sSL -o base.tgz https://codeload.github.com/teamshares/axn/tar.gz/8daba1dcb4e1f44e2a26c87e2d602c10fc04eca9
echo "## sha256"; sha256sum fc.tgz base.tgz
mkdir -p fc b; tar xzf fc.tgz -C fc --strip-components=1; tar xzf base.tgz -C b --strip-components=1
S0=fc/evidence/certify-rspec-g2/s0; V='./spec/axn/strategies_spec.rb[1:1:5:1]'; P='./spec/axn/strategies_spec.rb[1:1:2:3]'
echo "## R1 merged evidence integrity"; (cd fc/evidence/certify-rspec-g2 && sha256sum -c SHA256SUMS | grep -vc ': OK' || true)
echo "## R2 victim-first seeds where the victim still failed (from crosscheck)"; grep -E "^seed (16|24|26|27) " $S0/victim-first-crosscheck.txt | head -4
echo "## R3 victim failure message in those seeds"
for s in 16 24 26 27; do jq -r --arg v "$V" '.examples[]|select(.id==$v)|"seed '"$s"' \(.status) \(.exception.class): \(.exception.message)"' $S0/base-seed-$s.json; done
echo "## R4 base spec writers of Axn::Strategies outside shared examples (static grep)"
grep -rn "Strategies.register\|Strategies.clear!\|described_class.register(:custom" b/spec | grep -v shared_examples
echo "## R5 use_strategy_spec before hook registers :custom, no after"; sed -n 14,17p b/spec/axn/core/use_strategy_spec.rb; grep -c "after" b/spec/axn/core/use_strategy_spec.rb || true
echo "## R6 strategies_spec.rb:35 registers :custom, no cleanup at base"; sed -n 35,40p b/spec/axn/strategies_spec.rb
echo "## R7 contingency over 30 base seeds: victim status vs whether [1:3:1] (strategies_spec:35) and the named polluter ran before it"
for f in $S0/base-seed-*.json; do jq -r --arg v "$V" --arg p "$P" '.examples as $e|($e|map(.id)|index($v)) as $vi|($e[0:$vi]|map(.id)) as $pre|"victim=\($e[$vi].status) s35_before=\($pre|index("./spec/axn/strategies_spec.rb[1:3:1]")!=null) named_before=\($pre|index($p)!=null)"' $f; done | sort | uniq -c
echo "## R8 in the 4 seeds: index of [1:3:1], victim, and Strategies-touching files run between them"
for s in 16 24 26 27; do jq -r --arg v "$V" '.examples as $e|($e|map(.id)|index($v)) as $vi|($e|map(.id)|index("./spec/axn/strategies_spec.rb[1:3:1]")) as $pi|"seed '"$s"' s35=\($pi) victim=\($vi) between=\([$e[$pi:$vi][]|select(.file_path|test("use_strategy|vernier|client_spec|factory_spec|slack_sender|registry_behavior"))|.id]|unique)"' $S0/base-seed-$s.json; done
echo "## R9 use_strategy_spec examples before the victim in the 4 seeds (count)"
for s in 16 24 26 27; do jq -r --arg v "$V" '.examples as $e|($e|map(.id)|index($v)) as $vi|"seed '"$s"' use_strategy_before=\([$e[0:$vi][]|select(.file_path|test("use_strategy_spec"))]|length)"' $S0/base-seed-$s.json; done
