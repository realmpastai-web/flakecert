# PR check

One line per id in the seed-search union. OD verdicts use arm A.

| id | class | label | detail |
| --- | --- | --- | --- |
| ./spec/support/shared_examples/registry_behavior.rb:100 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=1 |
| ./spec/axn/tools/registry_spec.rb:299 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=1 |
| ./spec/axn/tools/registry_spec.rb:283 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=1 |
| ./spec/axn/tools/registry_spec.rb:237 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=1 |
| ./spec/axn/tools/registry_spec.rb:171 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=1 |
| ./spec/axn/extras/strategies/client_spec.rb:169 | BRITTLE | BRITTLE_CERTIFIED | enablers=1 seed=1 |
| ./spec/support/shared_examples/registry_behavior.rb:100 | ORDER-DEPENDENT | CERTIFIED | polluters=1 seed=3 |
| ./spec/axn/extras/strategies/client_spec.rb:175 | BRITTLE | BRITTLE_CERTIFIED | enablers=1 seed=3 |

## Skeptic pass

What else could move a verdict:
- Seeds searched are 1..30. An id that never fails in that range is not shown to be order-safe.
- The primary seed is the qualifying seed with the most base failures. Ties take the smallest seed. A different seed can fail a different set.
- An order-dependent certificate names one sufficient polluter set from rspec --bisect on the first seed where that id failed. Another sufficient set would not by itself change the cross-commit label.
- Bisect keeps one sufficient set when several exist. The certificate claims sufficiency of the recorded set.
- A brittle certificate names a 1-minimal enabler under defined order. Another sufficient set can exist. It does not claim to be the set a defined-order CI run relied on.
- The enabler search uses the predecessor ids from this base defined-order run. A different definition order would change that list.
- This run is Ruby 3.3 only. A pass here does not speak for the other CI Rubies.
- Alone results that are not 3/3 stay OTHER and are not a certificate.
- One order-dependent rep whose failed ids include a polluter id rejects that certificate.
- The message line is not part of the signature.
- An order-dependent id can be NOT_FIXED at base and FIXED at head and still stay UNRESOLVED when arm C does not pass 3/3 at both commits. Arm C passing at both commits would move that id to CERTIFIED. The same victim-only failure on arm C at head would move it toward CONTROL.
- Arm C requires tools/certify_rspec/ordering.rb and names the victim id before the polluter ids in ENV ids. The JSON example order is compared with that list. A mismatch is INVALID_ORDER and is not a pass or a fail, so the verdict cannot use it.
- At 5603142, arm C passed --order defined and listed the victim first. For two ids the JSON still ran the polluter id first. Those runs are ARM_C_INVALID_ORDER_BEFORE and are not certificates. A later arm C that matches the named order is a new measurement.
- A full-suite seed can run the victim before the recorded polluter and still fail, because other examples ran earlier. s0/victim-first-crosscheck.txt lists those seeds from the existing base json. It is not the isolated arm C pair.
- An id that never fails in the searched seeds is absent from the union. Absence is not evidence that the diff did nothing.
- Finding an enabler by search is not a market-novelty claim. No prior-art search was done.
- Star count on the subject repo is not evidence of demand. This run is a method proof.
