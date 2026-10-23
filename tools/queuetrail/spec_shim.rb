# frozen_string_literal: true

# Apply the recorded worker RNG seed. No-op when QUEUETRAIL_SRAND is unset.
# See docs/QUEUETRAIL-SPEC.md R4.

raw = ENV.fetch("QUEUETRAIL_SRAND", "")
srand(Integer(raw)) unless raw.empty?
