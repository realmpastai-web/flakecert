class Coupon
  def self.code
    format("%06d", rand(1_000_000))
  end

  def self.draw
    rand(2) == 1
  end
end
