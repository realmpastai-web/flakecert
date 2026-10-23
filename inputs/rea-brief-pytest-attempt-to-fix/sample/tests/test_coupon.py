import random


def test_coupon_draw():
    # RNG-only noise: fails about 1 run in 20 unless random is seeded
    assert random.randrange(20) != 0
