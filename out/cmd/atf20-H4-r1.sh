#!/bin/bash
ruby -v
bundle -v
printf "TARBALL_SHA256:%s\n" "$ATF_TARBALL_SHA256"
printf "COMMIT:%s\n" "$ATF_COMMIT"
'bundle' 'exec' 'rspec' '--format' 'documentation' '--no-color' '--require' './atf20/atf20_hook.rb' '--atf-n' '20' '--atf-case' 'H4' '--atf-commit' '148c1c9b4c041b1659ea633f2632dd47eef8cb04' '--atf-tarball' 'db53c7bc72519a447c11961956516a240472457042b28a6ea12f7138968390d5' '--atf-target' 'two_step_or_factor_client_spec.rb:76' '--atf-out' '/evidence/atf20/H4-r1.json' '--atf-audit' '/evidence/atf20/H4-r1.audit.json' '--atf-args' '["./spaceship/spec/two_step_or_factor_client_spec.rb:76"]' './spaceship/spec/two_step_or_factor_client_spec.rb:76'
ec=$?
chmod a+r '/evidence/atf20/H4-r1.json' '/evidence/atf20/H4-r1.audit.json' || true
echo "RSPEC_EXIT:$ec"
exit $ec
