require "test_helper"

class DeltaTest < ActiveSupport::TestCase
  test "delta one" do
    assert_equal 1, 1
  end

  test "delta two" do
    assert_equal 2, 1 + 1
  end

  test "delta three" do
    assert_equal 3, 1 + 2
  end

  test "delta four" do
    assert_equal "d", "d"
  end

  test "delta five" do
    assert_equal true, true
  end

  test "delta six" do
    assert_equal [], []
  end
end
