#!/usr/bin/env bash
# Static reverse for G3 (GitLab random-order backlog). Public artifacts only. Executes nothing from GitLab. Tools: curl, sha256sum, grep, sed, jq, python3.
set -euo pipefail
G=https://gitlab.com/gitlab-org/gitlab/-/raw
C=8004fe1c22e780c44d0db138293326037d847bf2   # master HEAD fetched 2026-10-19 18:10 IST
P=1502df8e80f36cb3e70e1e3e2f8cc13bc18ceeab   # last commit touching the todo before 2026-06-02 (2026-05-30)
curl -sSL -o todo-$C.yml       $G/$C/spec/support/rspec_order_todo.yml
curl -sSL -o failures-$C.yml   $G/$C/spec/support/rspec_order_failures.yml
curl -sSL -o rspec_order-$C.rb $G/$C/spec/support/rspec_order.rb
curl -sSL -o check-$C.sh       $G/$C/scripts/rspec_check_order_dependence
curl -sSL -o todo-$P.yml       $G/$P/spec/support/rspec_order_todo.yml
curl -sSL https://gitlab.com/api/v4/projects/278964/issues/601848 | jq -S . > issue-601848.json
curl -sSL https://gitlab.com/api/v4/projects/278964/issues/601849 | jq -S . > issue-601849.json
echo "## sha256 (pinned artifacts; issues are snapshots, mutable upstream)"; sha256sum todo-$C.yml failures-$C.yml rspec_order-$C.rb check-$C.sh todo-$P.yml issue-601848.json issue-601849.json
echo "## T1 todo entries at $C: total / ee / foss"; grep -c "^- '" todo-$C.yml; grep -c "^- './ee/" todo-$C.yml; grep -c "^- './spec/" todo-$C.yml
echo "## T2 todo entries at $P (2026-05-30): total / ee / foss"; grep -c "^- '" todo-$P.yml; grep -c "^- './ee/" todo-$P.yml; grep -c "^- './spec/" todo-$P.yml
echo "## T3 rspec_order_failures.yml entries at $C"; grep -c "^- '" failures-$C.yml || true
echo "## T4 issue metadata"; for i in 601848 601849; do jq -r '"\(.references.full) created=\(.created_at) updated=\(.updated_at) state=\(.state) author=\(.author.name) notes=\(.user_notes_count) labels=\(.labels|join(","))"' issue-$i.json; done
echo "## T5 #601848 claims"; jq -r .description issue-601848.json | grep -nE "FOSS spec files|Batch size|passing files per MR"
echo "## T6 #601849 excluded set (YAML block) and category counts"; jq -r .description issue-601849.json | sed -n '/^```yaml/,/^```/p' | grep "^- " | tee excl.txt | sed 's/.*# //'; echo "count=$(wc -l < excl.txt)"; grep -c "Category A" excl.txt; grep -c "Category B" excl.txt
echo "## T7 #601849 Category A definition (includes missing constant)"; jq -r .description issue-601849.json | grep -nE "fails even when run in|missing constant|Category B — |passes in defined order"
echo "## S1 check script phases: only the listed files run (\$@), --fail-fast, defined -> reverse -> N random, default N"; grep -nE "RSPEC_ARGS=|RANDOM_ORDER_RUNS=|rspec_run --order|RSPEC_ORDER=reverse|bin/rspec --bisect|sed -i.bak" check-$C.sh
echo "## S2 order selection: todo + failures files run defined; RSPEC_ORDER env overrides"; grep -nE "def order_for|order_from_env \|\||ENV\['RSPEC_ORDER'\]|:random unless|TODO_YAML =|FAILURE_YAML =" rspec_order-$C.rb
echo "## B1 bound for 0 failures in n random runs (one-sided 95% Clopper-Pearson upper = 1-0.05^(1/n))"
python3 -c "
for n in (5,10,30,59,299): print(n, f'{(1-0.05**(1/n))*100:.2f}%')"
