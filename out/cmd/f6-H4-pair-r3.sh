#!/bin/bash
ruby -v
bundle -v
printf "TARBALL_SHA256:%s\n" "$TARBALL_SHA256"
printf "COMMIT:%s\n" "$COMMIT"
'bundle' 'exec' 'rspec' '--format' 'documentation' '--no-color' '--seed' '48174' './spaceship/spec/two_step_or_factor_client_spec.rb:76:94'
ec=$?
echo "RSPEC_EXIT:$ec"
exit $ec
