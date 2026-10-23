require "test_helper"

class LocalePolluterTest < ActiveSupport::TestCase
  test "sets french and leaves it" do
    I18n.locale = :fr
    assert_equal :fr, I18n.locale
  end

  test "polluter neighbor stays quiet" do
    assert_equal 2, 1 + 1
  end
end
