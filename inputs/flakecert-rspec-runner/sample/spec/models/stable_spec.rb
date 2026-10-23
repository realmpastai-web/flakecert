require "spec_helper"

RSpec.describe "Stable controls" do
  it "adds" do
    expect(1 + 1).to eq(2)
  end

  it "formats" do
    expect(format("%03d", 7)).to eq("007")
  end
end
