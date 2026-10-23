# Spec G3: certificates for GitLab's random-order backlog (static reverse first)
Evidence: reverse/recon-gitlab.log (regenerate: reverse/recon-gitlab.sh), sources/ (issue snapshots, saved pages). Static only.
Hark executed nothing from GitLab. REA CLI was not needed: the targets are a YAML list, a bash script, a Ruby support file and issue JSON, so plain tools (curl, grep, sed, jq) are used, per the REA skill.

## Pinned artifacts (recon sha256 block)
- gitlab-org/gitlab master 8004fe1c22e780c44d0db138293326037d847bf2, fetched 2026-10-19 18:10 IST:
  - rspec_order_todo.yml 2d59f154...6a53
  - rspec_order_failures.yml 7d6decfd...829f
  - spec/support/rspec_order.rb 0346cc6d...e3f6
  - scripts/rspec_check_order_dependence 4438bc80...ba83
- Earlier todo at 1502df8e (2026-05-30): 2e21b0c3...c447.
- Issue snapshots #601848 (b365e591...b027) and #601849 (40027a9e...dd92). These are mutable upstream, so the frozen copies in sources/ are the evidence.
- Issue notes (5 on #601849) return 401 without sign-in. UNKNOWN; not read.

## Facts
- T1: the todo has 7,436 entries at 8004fe1c: 2,208 ee and 5,228 FOSS.
- T2: at 1502df8e there were 7,611 entries: 2,230 ee and 5,381 FOSS. So 153 FOSS entries were removed between 2026-05-30 and 2026-10-19.
- T3: rspec_order_failures.yml has 0 entries (comment header only).
- T4: both issues were opened 2026-06-02 by Peter Leitzen, labelled group::development tooling. Both were last updated 2026-06-17.
- T5: #601848 tells AI agents to check up to 50 candidates per run and target about 25 passing files per MR.
- T6: #601849 excludes 11 files: 10 Category A and 1 Category B1. The B1 file is spec/services/timelogs/delete_service_spec.rb. No Category A summary names a missing constant (asset compilation, Fog, before(:suite), setup, Vite).
- T7: Category A means "fails even when run in defined order". Its listed signs include missing constant.
- S1: the check runs ONLY the listed files ($@), with --fail-fast, in this sequence: defined, then RSPEC_ORDER=reverse, then RANDOM_ORDER_RUNS random runs (default 5).
  - On failure it runs `bin/rspec --bisect`, adding the seed if one was printed.
  - On a pass it deletes the file from the todo with sed.
- S2: rspec_order.rb runs files listed in the todo or failures YAML in defined order. ENV RSPEC_ORDER overrides this.
- B1: 0 failures in n runs gives a one-sided 95% upper bound of 1-0.05^(1/n): 5 runs 45.07%, 10 runs 25.89%, 30 runs 9.50%, 59 runs 4.95%, 299 runs 1.00%.

## Gaps (inferences; UNPROVEN until G3 runs)
- G-a (bound): a file leaves the todo after 0/5 random failures. That is a <=45.07% bound, and nothing records it.
- G-b (cross-file): S1 runs the file alone, so pollution from OTHER files (as in G2's registries) is out of the check's scope by construction.
- G-c (Category A): "fails alone in defined order" is treated as setup failure. A file that needs an enabler from another file (G2 BRITTLE) would land here.
  T6 shows no such case among the 10 named so far, so G-c is a hypothesis only.
- G-d (fix verdict): a fix is accepted on passing random runs. There is no base NOT_FIXED / head FIXED certificate.

## Certificate headline (product rule)
The first line of every FlakeCert certificate is the stated bound:
"0 failures in n seeded runs -> failure rate <= X% (one-sided 95%, Clopper-Pearson)", with n, the seeds and the pinned commit.
The verdict (CERTIFIED / BRITTLE_CERTIFIED / NOT_FIXED ...) comes second.

## G3 run plan (Step 2; needs Santhosh's go for GDK cost; holdout sealed now)
- Environment: GDK at 8004fe1c, recording the image/commit digests.
- S20: the 20 FOSS todo entries with the smallest sha256(path) among entries under ./spec/models/ or ./spec/lib/, computed from the frozen todo.
  Deterministic, and chosen by no human.
- Arm G: GitLab's own script per file (defined, reverse, 5 random), capturing its log.
- Arm F: FlakeCert per file, alone, seeds 1..30. The certificate headline bound comes from the actual pass count.
- Category A set: each of the 10 run alone in defined order, then inside full-suite defined order. A file that fails alone but passes in the suite goes to the G2 enabler search.
- B1 file: reverse order, then bisect.
Acceptance:
1. Every command and log is saved.
2. Certificates carry the bound headline.
3. No count without a log.
4. The holdout predictions-G3.json is scored once.
