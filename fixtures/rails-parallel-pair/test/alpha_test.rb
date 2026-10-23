require "test_helper"

class AlphaTest < ActiveSupport::TestCase
  test "alpha one" do
    assert_equal 1, 1
  end

  test "alpha two" do
    assert_equal 2, 1 + 1
  end

  test "alpha three" do
    assert_equal 3, 1 + 2
  end

  test "alpha four" do
    assert_equal "a", "a"
  end

  test "alpha five" do
    assert_equal true, true
  end

  test "alpha six" do
    assert_equal [], []
  end
end
