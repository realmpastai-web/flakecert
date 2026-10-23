# SPEC-G3.1 amendment (Santhosh, 2026-10-19 18:18 IST). Overrides SPEC-G3 where they differ. HOLDOUT-G3.sha256 is unchanged (cb3d3ccc...2d79).
1. Environment: use GitLab's own CI recipe at 8004fe1c, not GDK.
   - Image: DEFAULT_CI_IMAGE, resolved from .gitlab-ci.yml (gitlab-build-images ci/...-slim-ruby-${RUBY_VERSION}-...-postgresql-${PG_VERSION}, PG_VERSION "17").
   - Services: .db-services from .gitlab/ci/global.gitlab-ci.yml (gitlab-build-images:postgres-${PG_VERSION} with fsync=off etc., redis:7.2-alpine, plus gitlab-build-images:redis-cluster-${REDIS_CLUSTER_VERSION}).
   - Frozen copies: reverse/gitlab-ci-8004fe1c.yml and reverse/global.gitlab-ci-8004fe1c.yml.
   - Record every resolved image tag and its digest.
   - Fall back to full GDK only if an S20 spec fails because Gitaly is absent, with the log line saved.
2. Category A arm: the full-suite defined-order arm is DROPPED (GitLab's suite needs hundreds of CI nodes).
   - Run each of the 10 files (a) alone in defined order, then (b) with all *_spec.rb files in its own directory, in defined order.
   - A file that fails in (a) and passes in (b) goes to the enabler search (G2 method) within that directory only.
3. Holdout: any item whose test needed the full suite is scored N/A. Q3 is worded "inside the full-suite defined order", so it is N/A.
   Q5 is dated 2026-11-19 and is scored on that date. Q1, Q2 and Q4 are scored once after final evidence.
4. Budget: 4 hours wall. If env setup fails twice, stop and report with logs.
5. Cursor launches only after G2.2 lands, so the box is not split.
