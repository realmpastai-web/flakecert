#!/bin/bash
ruby -v
bundle -v
printf "TARBALL_SHA256:%s\n" "$ATF_TARBALL_SHA256"
printf "COMMIT:%s\n" "$ATF_COMMIT"
'bundle' 'exec' 'rspec' '--format' 'documentation' '--no-color' '--require' './atf20/atf20_hook.rb' '--atf-n' '20' '--atf-case' 'H2' '--atf-commit' '76eeb3f9352a657fd979ae00e89e49a388729e30' '--atf-tarball' '078c5e59b1765b88d829d9878b29deffb66e85122301a1f65d90b714bc81abaa' '--atf-target' 'build_beta_detail_spec.rb:5' '--atf-out' '/evidence/atf20/H2-r2.json' '--atf-audit' '/evidence/atf20/H2-r2.audit.json' '--atf-args' '["./spaceship/spec/connect_api/models/webhook_spec.rb", "./spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5"]' '--order' 'defined' './spaceship/spec/connect_api/models/webhook_spec.rb' './spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5'
ec=$?
chmod a+r '/evidence/atf20/H2-r2.json' '/evidence/atf20/H2-r2.audit.json' || true
echo "RSPEC_EXIT:$ec"
exit $ec
