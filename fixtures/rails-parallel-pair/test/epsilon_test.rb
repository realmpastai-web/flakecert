require "test_helper"

class EpsilonTest < ActiveSupport::TestCase
  test "epsilon one" do
    assert_equal 1, 1
  end

  test "epsilon two" do
    assert_equal 2, 1 + 1
  end

  test "epsilon three" do
    assert_equal 3, 1 + 2
  end

  test "epsilon four" do
    assert_equal "e", "e"
  end

  test "epsilon five" do
    assert_equal true, true
  end

  test "epsilon six" do
    assert_equal [], []
  end
end
