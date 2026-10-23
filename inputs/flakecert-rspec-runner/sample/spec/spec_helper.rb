# Mirrors the rspec-core 3.13.6 generated spec_helper defaults: no `config.order`,
# and `Kernel.srand config.seed` left disabled (it sits inside =begin/=end there).
$LOAD_PATH.unshift File.expand_path("../app/models", __dir__)
require "cart"
require "coupon"

RSpec.configure do |config|
  config.expect_with :rspec do |c|
    c.syntax = :expect
  end
end
