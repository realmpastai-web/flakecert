require "spec_helper"

RSpec.describe Cart do
  it "charges full price by default" do            # id ./spec/models/cart_spec.rb[1:1]  (victim)
    expect(Cart.new(100).total).to eq(100)
  end

  it "applies a promo discount" do                 # id ./spec/models/cart_spec.rb[1:2]  (polluter, never resets)
    Cart.default_discount = 10
    expect(Cart.new(100).total).to eq(90)
  end
end
