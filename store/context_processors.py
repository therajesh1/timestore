from .cart import Cart
from .content import NAV_CATEGORIES
from .models import Brand


def cart_summary(request):
    return {"cart_count": len(Cart(request))}


def brand_strip(request):
    return {"nav_brands": Brand.objects.filter(show_in_nav=True), "nav_categories": NAV_CATEGORIES}
