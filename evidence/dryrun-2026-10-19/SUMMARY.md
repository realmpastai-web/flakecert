# Dry run 2026-10-19 summary

Pins (full sha):

| short | full |
| --- | --- |
| eb925fa | eb925fa3f31eac8e70202debf565f1b32219e62d |
| aec7800 | aec7800d34c43eb6add78b895729c833ae4f4e0a |
| 76eeb3f | 76eeb3f9352a657fd979ae00e89e49a388729e30 |
| 148c1c9 | 148c1c9b4c041b1659ea633f2632dd47eef8cb04 |

Part 1 image `python:3.11`. `q1.log` line 257: `Python 3.11.17`. `q1.log` line 255: `Linux 6ce596449be0 6.12.94+ #1 SMP PREEMPT_DYNAMIC Fri Oct 16 00:53:04 UTC 2026 x86_64 GNU/Linux`. `q1.log` line 310: `pytest-randomly==4.1.0`. Every pytest command used `-p no:randomly --no-cov --junitxml=...`. `q1.log` has no `--randomly-seed`.

Part 2 image `ruby:3.1`. `q2.log` lines 3-4 and 26: `ruby 3.1.7p261 (2025-03-26 revision 0a3704f218) [x86_64-linux]`, `Bundler version 2.6.9`, `RSpec 3.12`. Seed on F1 and F2: `--seed 48174`.

Victim outcomes and e2e setup-error counts are the `VICTIM` and `E2E_SETUP_ERRORS` lines in `q1-junit-outcomes.log`. Leak counts are `grep -c 'has leaked into another example'` in `q2.log`.

A1 and A2 also have one non-victim assertion failure, `tests.e2e.test_bridge_live::test_shell_allowlist_keeps_legitimate_commands_working` at `tests/e2e/test_bridge_live.py:454`. That row is a `<failure>`, so the setup-error count stays 0. Example from `q1-junit-outcomes.log`: `failed	tests.e2e.test_bridge_live::test_shell_allowlist_keeps_legitimate_commands_working	tests/e2e/test_bridge_live.py:454`.

## Per-run table

| run id | sha | rep | victim outcome | assertion line if failed | e2e setup errors | leak count |
| --- | --- | --- | --- | --- | --- | --- |
| A0-eb925fa-r1 | eb925fa | 1 | passed |  | 0 | n/a |
| A0-eb925fa-r2 | eb925fa | 2 | passed |  | 0 | n/a |
| A0-eb925fa-r3 | eb925fa | 3 | passed |  | 0 | n/a |
| A1-eb925fa-r1 | eb925fa | 1 | passed |  | 0 | n/a |
| A1-eb925fa-r2 | eb925fa | 2 | passed |  | 0 | n/a |
| A1-eb925fa-r3 | eb925fa | 3 | passed |  | 0 | n/a |
| A2-eb925fa-r1 | eb925fa | 1 | passed |  | 0 | n/a |
| A2-eb925fa-r2 | eb925fa | 2 | passed |  | 0 | n/a |
| A2-eb925fa-r3 | eb925fa | 3 | passed |  | 0 | n/a |
| A0-aec7800-r1 | aec7800 | 1 | passed |  | 0 | n/a |
| A0-aec7800-r2 | aec7800 | 2 | passed |  | 0 | n/a |
| A0-aec7800-r3 | aec7800 | 3 | passed |  | 0 | n/a |
| A1-aec7800-r1 | aec7800 | 1 | passed |  | 0 | n/a |
| A1-aec7800-r2 | aec7800 | 2 | passed |  | 0 | n/a |
| A1-aec7800-r3 | aec7800 | 3 | passed |  | 0 | n/a |
| A2-aec7800-r1 | aec7800 | 1 | passed |  | 0 | n/a |
| A2-aec7800-r2 | aec7800 | 2 | passed |  | 0 | n/a |
| A2-aec7800-r3 | aec7800 | 3 | passed |  | 0 | n/a |
| S1-eb925fa-r01 | eb925fa | 1 | passed |  | 0 | n/a |
| S1-eb925fa-r02 | eb925fa | 2 | passed |  | 0 | n/a |
| S1-eb925fa-r03 | eb925fa | 3 | failed | tests/test_mcp_client_parity_v4_169_39.py:169 | 0 | n/a |
| S1-eb925fa-r04 | eb925fa | 4 | failed | tests/test_mcp_client_parity_v4_169_39.py:169 | 0 | n/a |
| S1-eb925fa-r05 | eb925fa | 5 | passed |  | 0 | n/a |
| S1-eb925fa-r06 | eb925fa | 6 | passed |  | 0 | n/a |
| S1-eb925fa-r07 | eb925fa | 7 | failed | tests/test_mcp_client_parity_v4_169_39.py:169 | 0 | n/a |
| S1-eb925fa-r08 | eb925fa | 8 | passed |  | 0 | n/a |
| S1-eb925fa-r09 | eb925fa | 9 | failed | tests/test_mcp_client_parity_v4_169_39.py:169 | 0 | n/a |
| S1-eb925fa-r10 | eb925fa | 10 | passed |  | 0 | n/a |
| S1-eb925fa-r11 | eb925fa | 11 | passed |  | 0 | n/a |
| S1-eb925fa-r12 | eb925fa | 12 | passed |  | 0 | n/a |
| S1-eb925fa-r13 | eb925fa | 13 | passed |  | 0 | n/a |
| S1-eb925fa-r14 | eb925fa | 14 | failed | tests/test_mcp_client_parity_v4_169_39.py:169 | 0 | n/a |
| S1-eb925fa-r15 | eb925fa | 15 | passed |  | 0 | n/a |
| S1-eb925fa-r16 | eb925fa | 16 | passed |  | 0 | n/a |
| S1-eb925fa-r17 | eb925fa | 17 | passed |  | 0 | n/a |
| S1-eb925fa-r18 | eb925fa | 18 | passed |  | 0 | n/a |
| S1-eb925fa-r19 | eb925fa | 19 | passed |  | 0 | n/a |
| S1-eb925fa-r20 | eb925fa | 20 | passed |  | 0 | n/a |
| F1-76eeb3f-r1 | 76eeb3f | 1 | suite: 913 examples, 31 failures | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |
| F1-76eeb3f-r2 | 76eeb3f | 2 | suite: 913 examples, 31 failures | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |
| F1-76eeb3f-r3 | 76eeb3f | 3 | suite: 913 examples, 31 failures | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |
| F2-148c1c9-r1 | 148c1c9 | 1 | suite: 913 examples, 1 failure | ./spaceship/spec/two_step_or_factor_client_spec.rb:76 | n/a | 0 |
| F2-148c1c9-r2 | 148c1c9 | 2 | suite: 913 examples, 1 failure | ./spaceship/spec/two_step_or_factor_client_spec.rb:76 | n/a | 0 |
| F2-148c1c9-r3 | 148c1c9 | 3 | suite: 913 examples, 1 failure | ./spaceship/spec/two_step_or_factor_client_spec.rb:76 | n/a | 0 |
| F3-76eeb3f-r1 | 76eeb3f | 1 | 1 example, 1 failure | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |
| F3-76eeb3f-r2 | 76eeb3f | 2 | 1 example, 1 failure | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |
| F3-76eeb3f-r3 | 76eeb3f | 3 | 1 example, 1 failure | ./spaceship/spec/spaceauth_spec.rb:7 | n/a | 0 |

S1 failure text in `q1-junit-outcomes.log`: `AssertionError: assert ['/usr/local/..., '--version'] == ['node', 'server.js']`.

F3 failure class in `rspec/F3-76eeb3f-r1.log` line 18: `WebMock::NetConnectNotAllowedError:`.

F1 r1 `grep -c` in `q2.log` lines 34-35:

```
+ grep -c 'has leaked into another example' rspec/F1-76eeb3f-r1.log
0
```

Same `0` for F1 r2 (`q2.log` 79-80), F1 r3 (124-125), F2 r1/r2/r3 (appended `q2-f2.log` section), and F3 r1/r2/r3 (173-174, 203-204, 233-234).

No macOS run. No seed search after the F1 leak count was 0.
