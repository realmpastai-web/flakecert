DEFAULT_DISCOUNT = None


class Cart:
    def __init__(self, items):
        self.items = list(items)

    def total(self):
        subtotal = sum(self.items)
        if DEFAULT_DISCOUNT:
            return subtotal * (100 - DEFAULT_DISCOUNT) // 100
        return subtotal
