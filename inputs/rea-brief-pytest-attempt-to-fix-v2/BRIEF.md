# Gate v2: pytest Attempt-to-Fix (internal, frozen by Hark 2026-10-18)

Why: PR #7 (3ec5eb8) went NO-GO on wrong_fix.sig_equals_cert. wrong_fix.patch inserts one line above the victim,
so the same `assert 90 == 100` moves from tests/test_cart.py:6 to :7, and failure_signature (it hashes the
normalized traceback, line numbers included) changes from 40c3f885... to fe53cdfb.... That expectation was the v1
freeze's error: the RSpec gate (inputs/flakecert-attempt-to-fix/gate_attempt_to_fix.py:119) checks the sig on prefix
only, and v1's synthetic-good gave wrong_fix the cert's sig ("a"*64), so its self-check could not catch it.

Ruling (agreed by Santhosh 2026-10-18): keep failure_signature and prefix.sig_equals_cert exact. Add tb_norm.
Replace the wrong_fix check with wrong_fix.same_failure_modulo_line, which requires all of:
  tb_norm hashes to its own sig; masked tb_norm (`.py:<n>` -> `.py:LINE`) equals the cert's; the raw sig differs;
  every tests/test_cart.py line shifts by exactly the lines wrong_fix inserts above the victim (1, computed from the
  frozen fix files); no frame outside tests/test_cart.py; exc and 0x-masked message equal the prefix replay.

v1 (inputs/rea-brief-pytest-attempt-to-fix, 2560b40) is read in place and its 41-file SHA256SUMS is checked by the v2
self-check. Not claimed: that the pytest gap is proven. That needs B3 GATE PASS on the pinned image.
