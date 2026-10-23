#!/bin/bash
ruby -v
bundle -v
printf "TARBALL_SHA256:%s\n" "$TARBALL_SHA256"
printf "COMMIT:%s\n" "$COMMIT"
'bundle' 'exec' 'rspec' '--format' 'documentation' '--no-color' '--order' 'defined' './spaceship/spec/connect_api/models/build_beta_detail_spec.rb:5' './spaceship/spec/connect_api/models/webhook_spec.rb'
ec=$?
echo "RSPEC_EXIT:$ec"
exit $ec
