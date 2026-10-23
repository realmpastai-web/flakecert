require_relative "boot"

require "rails"
require "active_model/railtie"
require "active_job/railtie"
require "action_controller/railtie"
require "action_view/railtie"
require "rails/test_unit/railtie"
require "active_support/railtie"

Bundler.require(*Rails.groups)

module ParallelPair
  class Application < Rails::Application
    config.load_defaults 8.1
    config.i18n.available_locales = [:en, :fr]
    config.eager_load = false
    config.cache_classes = true
    config.secret_key_base = "fixture-only-secret-key-base-not-for-production-use-00"
    config.logger = Logger.new(IO::NULL)
    config.active_support.deprecation = :stderr
  end
end
