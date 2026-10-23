# CURSOR TASK: FlakeCert certify-rspec G1 (certify-the-fix PR check, RSpec)
Goal: build `flakecert certify-rspec` and validate it on fastlane#30184 per inputs/dryrun-2026-10-19-g1/SPEC-certify-rspec-G1.md.
No pytest, no pytest-randomly execution. Static reading of fastlane is fine; execution only inside the F4/F6 docker image.
1. `cd inputs/dryrun-2026-10-19-g1 && sha256sum -c SHA256SUMS` all OK; do not edit the folder. Replay `bash reverse/recon-bisect.sh`
   in an empty dir; its sha256 lines must equal reverse/recon-bisect.log lines 2-3.
2. Implement in flakecert (branch feat/certify-rspec-g1 from main f338f24): `tools/certify_rspec/` (Python 3.11, stdlib only) with
   CLI `python -m tools.certify_rspec --base-url <codeload tgz> --head-url <codeload tgz> --suite spaceship/spec --seed 48174
   --image <docker image> --out <dir>`, doing S1-S5 exactly. It must not take victim or polluter names as input.
   Unit tests in tests/ for: S2 classification rule, S4 verdict rule (incl. rep-disagreement), certificate schema, replay.sh
   round-trip on a canned log fixture. Root `python3 -m pytest -q` must stay green (CI verify).
3. Run it on fastlane base 76eeb3f9352a657fd979ae00e89e49a388729e30 / head 148c1c9b4c041b1659ea633f2632dd47eef8cb04, seed 48174.
   Save under evidence/certify-rspec-g1/: run.log (all commands + outputs, argv lengths, ruby/bundle/rspec versions, image id),
   s1.json, s2/, s3/<victim>-bisect.log, s4/<victim>-<sha7>-<A|B|C>-r<k>.log, cert-<n>.json, replay.sh per cert,
   replay-check.log (second replay of every cert), check-summary.md, SHA256SUMS.
4. g1.log must end with: OD_COUNT n, ATTRIBUTED n, CERTIFIED ids, CONTROL ids, ACCEPTANCE_1..4 True/False, GO True/False,
   and the grep output for acceptance 1.
5. Open a draft PR. If a step loops more than twice, stop and report what you have.
