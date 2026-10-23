require "test_helper"

class BetaTest < ActiveSupport::TestCase
  test "beta one" do
    assert_equal 1, 1
  end

  test "beta two" do
    assert_equal 2, 1 + 1
  end

  test "beta three" do
    assert_equal 3, 1 + 2
  end

  test "beta four" do
    assert_equal "b", "b"
  end

  test "beta five" do
    assert_equal true, true
  end

  test "beta six" do
    assert_equal [], []
  end
end
