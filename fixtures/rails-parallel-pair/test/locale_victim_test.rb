require "test_helper"

class LocaleVictimTest < ActiveSupport::TestCase
  test "expects english greeting" do
    assert_equal :en, I18n.locale
    assert_equal "Hello", I18n.t("greeting")
  end

  test "victim neighbor stays quiet" do
    assert_equal 3, 1 + 2
  end
end
