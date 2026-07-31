from decimal import Decimal

from .models import Product

SESSION_KEY = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(SESSION_KEY)
        if cart is None:
            cart = self.session[SESSION_KEY] = {}
        self.cart = cart

    def add(self, product, quantity=1):
        product_id = str(product.pk)
        if product_id in self.cart:
            self.cart[product_id] += quantity
        else:
            self.cart[product_id] = quantity
        self.save()

    def remove(self, product):
        product_id = str(product.pk)
        if product_id in self.cart:
            del self.cart[product_id]
            self.save()

    def save(self):
        self.session.modified = True

    def clear(self):
        self.session[SESSION_KEY] = {}
        self.save()

    def __iter__(self):
        product_ids = self.cart.keys()
        products = Product.objects.filter(pk__in=product_ids)
        products_by_id = {str(p.pk): p for p in products}
        for product_id, quantity in self.cart.items():
            product = products_by_id.get(product_id)
            if not product:
                continue
            yield {
                "product": product,
                "quantity": quantity,
                "line_total": product.price * quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    def total(self):
        return sum(item["line_total"] for item in self)
