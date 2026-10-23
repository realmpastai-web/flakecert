require "spec_helper"

RSpec.describe Coupon do
  it "generates a six-digit code" do               # stable
    expect(Coupon.code).to match(/\A\d{6}\z/)
  end

  it "draws a winning ticket" do                   # RNG-dependent: fails when rand(2) == 0
    expect(Coupon.draw).to be(true)
  end
end
