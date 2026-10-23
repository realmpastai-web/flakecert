import sys

from tools.certify_rspec.pipeline import main

if len(sys.argv) > 1 and sys.argv[1] == "rejudge":
    from tools.certify_rspec.rejudge import main as rejudge_main

    sys.exit(rejudge_main(sys.argv[2:]))
if len(sys.argv) > 1 and sys.argv[1] == "discover":
    from tools.certify_rspec.pipeline_g2 import main as discover_main

    sys.exit(discover_main(sys.argv[2:]))
if len(sys.argv) > 1 and sys.argv[1] == "cause":
    from tools.certify_rspec.pipeline_g22 import main as cause_main

    sys.exit(cause_main(sys.argv[2:]))
sys.exit(main())
