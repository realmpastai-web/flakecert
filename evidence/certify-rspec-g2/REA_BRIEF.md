# REA brief: arm C order for certify-rspec G2.1

Target: rspec-core 3.13.2 as installed for the G2 run (evidence/certify-rspec-g2/run.log, `rspec-core 3.13.2`), image digest `ruby@sha256:0a5633bcfe247d312edbc1e1c4a048ae3f5a99bea482af2d484b036c09cbd5a4`. Gem inspected at `/tmp/flakecert-g2-1019/probe/bundle/ruby/3.3.0/gems/rspec-core-3.13.2`. No code was copied from that gem.

## Observed

- `tools/certify_rspec/commands.py` arm C (at 5603142) is `rspec --order defined` with the victim id before the polluter ids.
- `evidence/certify-rspec-g2/s4/spec_support_shared_examples_registry_behavior.rb-100-74084bed-8daba1d-C-r1.json` records `include {:ids=>{"./spec/axn/async/registry_spec.rb"=>["1:1:5:1", "1:1:2:1"]}}` and then runs `./spec/axn/async/registry_spec.rb[1:1:2:1]` (passed) before `./spec/axn/async/registry_spec.rb[1:1:5:1]` (failed). The same swap is in the r2 and r3 files for that stem, and in the matching head `6c62d56` C files (both examples passed, polluter id first). The strategies victim `./spec/axn/strategies_spec.rb[1:1:5:1]` has the same swap against polluter `./spec/axn/strategies_spec.rb[1:1:2:3]` in its six C files.
- The four tools/registry C files already run the victim id before its polluter id.
- rspec-core `ConfigurationOptions::OPTIONS_ORDER` applies `:order` before `:requires`. `Ordering::ConfigurationManager#register_ordering` does not replace `:global` once order has been forced. `--order` and `--seed` both force it. A require file that calls `register_ordering(:global)` therefore does not run when the argv also passes `--order` or `--seed`.
- `ExampleGroup.run` orders filtered examples and child groups separately, and runs the direct examples before the child groups. Child groups are ordered by the group's ordering strategy. `:global` is the strategy when a group has no `:order` metadata (`example_group.rb` `ordering_strategy`). `World#ordered_example_groups` orders top-level groups with the global strategy.
- The block passed to `register_ordering` must return the reordered array (`Ordering::Custom#order` returns the block result). The installed docs say the block receives examples or groups.

## Build rule

- Arm C is `rspec --require /flakecert/ordering.rb <victim> <polluters>` with `ENV["ids"]` set to that same id list. No `--order`.
- `tools/certify_rspec/ordering.rb` calls `RSpec.configure` / `register_ordering(:global)`. An example's rank is its index in `ENV["ids"]`. A group's rank is the minimum rank of its descendants. Unlisted ids sort after listed ids and keep their original relative order.
- After every A/B/C (and brittle alone/enabled) run, compare the JSON example ids to the id list that arm named. A difference is `INVALID_ORDER`, which is neither a pass nor a fail, and the verdict must not use that arm.

## Gate

Re-run S4 arm C, 3 reps, base and head, for all six order-dependent victims, on the same image digest. The four previously CERTIFIED ids stay CERTIFIED unless a new run says otherwise. The two ids above settle as CERTIFIED or REJECTED. `summary.json` `exit_ok` is true. `ARM_C_INVALID_ORDER_AFTER` counts C runs whose JSON order still differs.

## Unknown until the re-run

Whether victim-then-polluter passes 3/3 at base for the two ids. Full-suite seeds where the victim happens to start before this polluter are not that measurement: other examples may have run earlier. Those seeds are listed from existing `s0/base-seed-*.json` only.
