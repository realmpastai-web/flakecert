ENV["RAILS_ENV"] ||= "test"

require_relative "../config/environment"
require "rails/test_help"

module ActiveSupport
  class TestCase
    # threshold is 1 because ActiveSupport's default is 50 and this suite
    # has fewer tests than that. See PAIR.md.
    parallelize(workers: 4, threshold: 1)
  end
end

# Opt-in. Stock runs leave QUEUETRAIL_RAILS unset and do not load the hook.
if ENV["QUEUETRAIL_RAILS"] == "1"
  require File.expand_path("../../../tools/queuetrail/rails", __dir__)
end
