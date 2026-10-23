from app import cart
from app.cart import Cart
cart.DEFAULT_DISCOUNT = None  # reset once, at import


def test_total_without_discount():
    assert Cart([60, 40]).total() == 100


def test_total_with_discount():
    cart.DEFAULT_DISCOUNT = 10
    assert Cart([60, 40]).total() == 90
