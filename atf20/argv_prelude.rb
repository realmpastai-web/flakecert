# frozen_string_literal: true

# Loaded with RUBYOPT before the runner parses ARGV.
# Moves harness flags into the environment so the runner's own parser
# never sees them. The harness itself is loaded later with --require.

module Atf20Argv
  FLAGS = {
    "--atf-n" => "ATF_N",
    "--atf-case" => "ATF_CASE",
    "--atf-commit" => "ATF_COMMIT",
    "--atf-tarball" => "ATF_TARBALL_SHA256",
    "--atf-target" => "ATF_TARGET",
    "--atf-out" => "ATF_OUT",
    "--atf-audit" => "ATF_AUDIT",
    "--atf-args" => "ATF_ARGS",
  }.freeze

  def self.consume!(argv)
    kept = []
    index = 0
    while index < argv.length
      flag = argv[index]
      env_key = FLAGS[flag]
      if env_key
        value = argv[index + 1]
        raise "missing value for #{flag}" if value.nil?
        ENV[env_key] = value
        index += 2
      else
        kept << flag
        index += 1
      end
    end
    argv.replace(kept)
  end
end

Atf20Argv.consume!(ARGV)
