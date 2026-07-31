from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .content import FEATURES, GENDER_TILES, HERO_SLIDES
from .forms import BrandForm, CheckoutForm, OrderStatusForm, ProductForm, RegisterForm, SubBrandForm
from .models import Brand, Order, OrderItem, Product, SubBrand


def home(request):
    wrist_watches = Product.objects.filter(category=Product.Category.WRIST_WATCH)[:4]
    smart_watches = Product.objects.filter(category=Product.Category.SMART_WATCHS)[:4]
    context = {
        "hero_slides": HERO_SLIDES,
        "gender_tiles": GENDER_TILES,
        "features": FEATURES,
        "wrist_watches": wrist_watches,
        "smart_watches": smart_watches,
    }
    return render(request, "store/home.html", context)


def product_list(request):
    products = Product.objects.select_related("brand").all()
    category = request.GET.get("category", "")
    query = request.GET.get("q", "")
    brand_slug = request.GET.get("brand", "")

    valid_categories = [choice[0] for choice in Product.Category.choices]
    if category in valid_categories:
        products = products.filter(category=category)
    if query:
        products = products.filter(name__icontains=query) | products.filter(description__icontains=query)

    selected_brand = None
    if brand_slug:
        selected_brand = Brand.objects.filter(slug=brand_slug).first()
        products = products.filter(brand__slug=brand_slug)

    context = {
        "products": products,
        "category": category,
        "categories": valid_categories,
        "query": query,
        "selected_brand": selected_brand,
    }
    return render(request, "store/product_list.html", context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    return render(request, "store/product_detail.html", {"product": product, "related": related})


@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = Cart(request)
    cart.add(product)
    messages.success(request, f"{product.name} added to your cart.")
    return redirect(request.POST.get("next", "cart_detail"))


@require_POST
def cart_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = Cart(request)
    cart.remove(product)
    return redirect("cart_detail")


def cart_detail(request):
    cart = Cart(request)
    return render(request, "store/cart.html", {"cart": cart})


@login_required
def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.info(request, "Your cart is empty.")
        return redirect("product_list")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                user=request.user,
                shipping_address=form.cleaned_data["shipping_address"],
                total=cart.total(),
            )
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item["product"],
                    quantity=item["quantity"],
                    price=item["product"].price,
                )
            cart.clear()
            messages.success(request, f"Order #{order.pk} placed successfully.")
            return redirect("order_history")
    else:
        initial = {"shipping_address": request.user.profile.address}
        form = CheckoutForm(initial=initial)

    return render(request, "store/checkout.html", {"cart": cart, "form": form})


@login_required
def order_history(request):
    orders = request.user.orders.prefetch_related("items__product")
    return render(request, "store/orders.html", {"orders": orders})


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Welcome to The Time Store.")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@staff_member_required
def dashboard(request):
    products = Product.objects.all()
    orders = Order.objects.all()
    revenue = orders.aggregate(total=Sum("total"))["total"] or Decimal("0")
    
    category_counts = {
        cat[0]: products.filter(category=cat[0]).count()
        for cat in Product.Category.choices
    }
    
    context = {
        "product_count": products.count(),
        "category_counts": category_counts,
        "order_count": orders.count(),
        "revenue": revenue,
        "recent_orders": orders.select_related("user")[:8],
        "low_stock": products.filter(stock__lte=2),
    }
    return render(request, "store/dashboard.html", context)


@staff_member_required
def product_manage_list(request):
    products = Product.objects.select_related("brand", "sub_brand").all()
    query = request.GET.get("q", "")
    category = request.GET.get("category", "")
    if query:
        products = products.filter(name__icontains=query) | products.filter(ref__icontains=query)
    if category:
        products = products.filter(category=category)
    return render(request, "store/manage_products.html", {
        "products": products,
        "query": query,
        "categories": Product.Category.choices,
        "selected_category": category,
    })


def _next_product_ref():
    count = Product.objects.count()
    next_ref = str(count + 1)
    while Product.objects.filter(ref=next_ref).exists():
        count += 1
        next_ref = str(count + 1)
    return next_ref


SIMPLE_CATEGORIES = {
    Product.Category.WALL_CLOCKS,
    Product.Category.PERFUMES,
    Product.Category.ACCESSORIES,
}


@staff_member_required
def product_create(request):
    selected_category = request.GET.get("category", Product.Category.WRIST_WATCH)
    if request.method == "POST":
        selected_category = request.POST.get("category", selected_category)
        form = ProductForm(request.POST, request.FILES, simple=selected_category in SIMPLE_CATEGORIES)
        if form.is_valid():
            product = form.save(commit=False)
            product.ref = _next_product_ref()
            product.save()
            messages.success(request, f"{product.name} added to the catalog.")
            return redirect("product_manage_list")
    else:
        form = ProductForm(
            initial={"ref": _next_product_ref(), "category": selected_category},
            simple=selected_category in SIMPLE_CATEGORIES,
        )
    return render(request, "store/product_form.html", {
        "form": form, "is_new": True,
        "categories": Product.Category.choices, "selected_category": selected_category,
    })


@staff_member_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    is_simple = product.category in SIMPLE_CATEGORIES
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product, simple=is_simple)
        if form.is_valid():
            form.save()
            messages.success(request, f"{product.name} updated.")
            return redirect("product_manage_list")
    else:
        form = ProductForm(instance=product, simple=is_simple)
    return render(request, "store/product_form.html", {
        "form": form, "is_new": False, "product": product,
        "categories": Product.Category.choices, "selected_category": product.category,
    })


@staff_member_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f"{name} was deleted.")
        return redirect("product_manage_list")
    return render(request, "store/product_confirm_delete.html", {"product": product})


@staff_member_required
def brand_manage_list(request):
    brands = Brand.objects.all()
    category = request.GET.get("category", "")
    if category:
        brands = brands.filter(products__category=category).distinct()
    if request.method == "POST" and "add_subbrand" in request.POST:
        form = BrandForm()
        subbrand_form = SubBrandForm(request.POST)
        if subbrand_form.is_valid():
            sub_brand = subbrand_form.save()
            messages.success(request, f"Sub-brand “{sub_brand.name}” added to {sub_brand.brand.name}.")
            return redirect("brand_manage_list")
    elif request.method == "POST":
        form = BrandForm(request.POST, request.FILES)
        subbrand_form = SubBrandForm()
        if form.is_valid():
            brand = form.save()
            messages.success(request, f"Brand “{brand.name}” added.")
            return redirect("brand_manage_list")
    else:
        form = BrandForm()
        subbrand_form = SubBrandForm()
    return render(request, "store/manage_brands.html", {
        "brands": brands, "form": form, "subbrand_form": subbrand_form,
        "categories": Product.Category.choices, "selected_category": category,
    })


@staff_member_required
def brand_detail(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == "POST":
        if "save_brand" in request.POST:
            form = BrandForm(request.POST, request.FILES, instance=brand)
            if form.is_valid():
                form.save()
                messages.success(request, "Brand updated.")
                return redirect("brand_detail", pk=brand.pk)
            subbrand_form = SubBrandForm(initial={"brand": brand})
        else:
            form = BrandForm(instance=brand)
            subbrand_form = SubBrandForm(request.POST)
            if subbrand_form.is_valid():
                sub_brand = subbrand_form.save()
                messages.success(request, f"Sub-brand “{sub_brand.name}” added to {sub_brand.brand.name}.")
                return redirect("brand_detail", pk=sub_brand.brand_id)
    else:
        form = BrandForm(instance=brand)
        subbrand_form = SubBrandForm(initial={"brand": brand})
    return render(request, "store/brand_detail.html", {
        "brand": brand,
        "form": form,
        "subbrand_form": subbrand_form,
        "sub_brands": brand.sub_brands.all(),
    })


@staff_member_required
@require_POST
def subbrand_delete(request, pk):
    sub_brand = get_object_or_404(SubBrand, pk=pk)
    brand_pk = sub_brand.brand_id
    sub_brand.delete()
    messages.success(request, "Sub-brand removed.")
    return redirect("brand_detail", pk=brand_pk)


@staff_member_required
def order_manage_list(request):
    orders = Order.objects.select_related("user").all()
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")
    if status:
        orders = orders.filter(status=status)
    if category:
        orders = orders.filter(items__product__category=category).distinct()
    return render(request, "store/manage_orders.html", {
        "orders": orders, "status": status, "statuses": Order.Status.choices,
        "categories": Product.Category.choices, "selected_category": category,
    })


@staff_member_required
def order_manage_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items__product"), pk=pk)
    if request.method == "POST":
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f"Order #{order.pk} status updated to {order.status}.")
            return redirect("order_manage_detail", pk=order.pk)
    else:
        form = OrderStatusForm(instance=order)
    return render(request, "store/order_manage_detail.html", {"order": order, "form": form})
