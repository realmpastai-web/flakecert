# Rails-layout model (plain Ruby; no Rails gem). Class-level state = the classic leak.
class Cart
  class << self
    attr_accessor :default_discount
  end

  def initialize(subtotal)
    @subtotal = subtotal
  end

  def total
    @subtotal - (self.class.default_discount || 0)
  end
end
