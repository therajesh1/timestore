from decimal import Decimal
import csv
import io
import re
import threading
import requests
from PIL import Image
from django.core.files.base import ContentFile
from django.http import HttpResponse

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .content import FEATURES, GENDER_TILES, HERO_SLIDES
from .forms import BrandForm, CheckoutForm, OrderStatusForm, ProductForm, RegisterForm, SubBrandForm, ProductColorFormSet
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
    subbrand_id = request.GET.get("subbrand", "")

    valid_categories = [choice[0] for choice in Product.Category.choices]
    if category in valid_categories:
        products = products.filter(category=category)
    if query:
        products = products.filter(name__icontains=query) | products.filter(description__icontains=query)

    selected_brand = None
    sub_brands = None
    selected_subbrand = None

    if brand_slug:
        selected_brand = Brand.objects.filter(slug=brand_slug).first()
        if selected_brand:
            products = products.filter(brand=selected_brand)
            sub_brands = selected_brand.sub_brands.all()
            if subbrand_id:
                selected_subbrand = sub_brands.filter(pk=subbrand_id).first()
                if selected_subbrand:
                    products = products.filter(sub_brand=selected_subbrand)

    context = {
        "products": products,
        "category": category,
        "categories": valid_categories,
        "query": query,
        "selected_brand": selected_brand,
        "sub_brands": sub_brands,
        "selected_subbrand": selected_subbrand,
    }
    return render(request, "store/product_list.html", context)


def product_detail(request, pk):
    from difflib import SequenceMatcher
    product = get_object_or_404(Product, pk=pk)
    
    # Get all other products
    candidates = list(Product.objects.exclude(pk=product.pk))
    ref_model = (product.model_number or "").strip().lower()
    
    scored_candidates = []
    for cand in candidates:
        cand_model = (cand.model_number or "").strip().lower()
        
        # Calculate model number similarity ratio
        if ref_model and cand_model:
            model_sim = SequenceMatcher(None, ref_model, cand_model).ratio()
        else:
            model_sim = 0.0
            
        # Category bonus (relevance)
        cat_bonus = 0.5 if cand.category == product.category else 0.0
        
        # Brand bonus (relevance)
        brand_bonus = 0.3 if cand.brand_id and cand.brand_id == product.brand_id else 0.0
        
        # Prioritize model similarity strongly, then category/brand
        score = model_sim * 2.0 + cat_bonus + brand_bonus
        scored_candidates.append((score, cand))
        
    # Sort by score descending and get top 4
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    related = [item[1] for item in scored_candidates[:4]]
    
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
    Product.Category.SMART_WATCHS,
    Product.Category.KIDS,
}


@staff_member_required
def product_create(request):
    selected_category = request.GET.get("category", Product.Category.WRIST_WATCH)
    is_simple = selected_category in SIMPLE_CATEGORIES
    if request.method == "POST":
        selected_category = request.POST.get("category", selected_category)
        is_simple = selected_category in SIMPLE_CATEGORIES
        form = ProductForm(request.POST, request.FILES, simple=is_simple)
        formset = ProductColorFormSet(request.POST, request.FILES, prefix="custom_colors") if not is_simple else None
        if form.is_valid() and (is_simple or formset.is_valid()):
            product = form.save(commit=False)
            product.ref = _next_product_ref()
            if is_simple:
                default_brand, _ = Brand.objects.get_or_create(
                    name="Generic",
                    defaults={"show_in_nav": False}
                )
                product.brand = default_brand
            product.save()
            if not is_simple:
                formset.instance = product
                formset.save()
            messages.success(request, f"{product.name} added to the catalog.")
            return redirect("product_manage_list")
    else:
        form = ProductForm(
            initial={"ref": _next_product_ref(), "category": selected_category},
            simple=is_simple,
        )
        formset = ProductColorFormSet(prefix="custom_colors") if not is_simple else None
    return render(request, "store/product_form.html", {
        "form": form, "formset": formset, "is_new": True,
        "categories": Product.Category.choices, "selected_category": selected_category,
    })


@staff_member_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    is_simple = product.category in SIMPLE_CATEGORIES
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product, simple=is_simple)
        formset = ProductColorFormSet(request.POST, request.FILES, instance=product, prefix="custom_colors") if not is_simple else None
        if form.is_valid() and (is_simple or formset.is_valid()):
            form.save()
            if not is_simple:
                formset.save()
            messages.success(request, f"{product.name} updated.")
            return redirect("product_manage_list")
    else:
        form = ProductForm(instance=product, simple=is_simple)
        formset = ProductColorFormSet(instance=product, prefix="custom_colors") if not is_simple else None
    return render(request, "store/product_form.html", {
        "form": form, "formset": formset, "is_new": False, "product": product,
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
        subbrand_form = SubBrandForm(request.POST, request.FILES)
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
            subbrand_form = SubBrandForm(request.POST, request.FILES)
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


def upgrade_image_url(url):
    """
    Upgrades known retailer, marketplace, and stock image URLs to high-resolution master versions.
    """
    if not url:
        return url
    u = url.strip()
    
    # 1. Unsplash: request 1800px width with 90% quality & WebP/AVIF auto-formatting
    if "images.unsplash.com" in u:
        if "w=" in u:
            u = re.sub(r"w=\d+", "w=1800", u)
        else:
            u += ("&" if "?" in u else "?") + "w=1800"
        if "auto=format" not in u:
            u += "&auto=format"
        if "q=" not in u:
            u += "&q=90"
        return u
        
    # 2. SwissTimeHouse / PrestaShop: upgrade thumbnails to thickbox_default (high-res master)
    if any(k in u for k in ["medium_default", "home_default", "small_default"]):
        for k in ["medium_default", "home_default", "small_default"]:
            u = u.replace(k, "thickbox_default")
        return u
        
    # 3. Amazon: strip dynamic resize downsampling tokens (e.g. ._AC_UL320_.) to fetch original master
    if "media-amazon.com" in u or "images-amazon.com" in u:
        u = re.sub(r"\._[A-Z0-9_,]+_\.", "._UL1500_.", u)
        return u
        
    # 4. Flipkart: upgrade thumbnail dimensions to 1600x1600
    if "flixcart.com" in u:
        u = re.sub(r"/image/\d+/\d+/", "/image/1600/1600/", u)
        return u
        
    # 5. Myntra: request 1440px wide master
    if "myntassets.com" in u:
        u = re.sub(r"w_\d+", "w_1440", u)
        return u

    # 6. Nykaa CDN: upgrade thumbnail to 1200px
    if "nykaa.com" in u:
        u = re.sub(r"tr=w-\d+", "tr=w-1200", u)
        return u
        
    return u


def _download_image_content(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    upgraded = upgrade_image_url(url)
    try:
        resp = requests.get(upgraded, headers=headers, timeout=18)
        if resp.status_code == 200 and len(resp.content) > 1000:
            return resp.content, upgraded
    except Exception:
        pass
        
    # Fallback to original URL if upgraded URL failed
    if upgraded != url:
        try:
            resp = requests.get(url, headers=headers, timeout=18)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content, url
        except Exception:
            pass
            
    return None, None


def _upload_image_from_url(url, field, product_name="", row_num=None):
    if not url or not url.startswith(("http://", "https://")):
        return False, None

    warnings = []
    if "encrypted-tbn0.gstatic.com" in url:
        warnings.append(
            f"Row {row_num or '?'}: Google search preview thumbnail URL detected for '{product_name}'. "
            f"Google thumbnails are low resolution (~300px). For best quality, use direct retailer or brand product image URLs."
        )

    content, final_url = _download_image_content(url)
    if not content:
        fail_msg = f"Row {row_num or '?'}: Failed to download image for '{product_name}' from {url[:60]}..."
        warnings.append(fail_msg)
        return False, " | ".join(warnings)

    # Check image resolution with Pillow
    try:
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        if w < 500 or h < 500:
            warnings.append(
                f"Row {row_num or '?'}: Low image resolution for '{product_name}' ({w}×{h}px). "
                f"Recommended minimum for luxury watches is at least 1000×1000px."
            )
    except Exception:
        pass

    try:
        name = final_url.split("/")[-1].split("?")[0]
        if not name or "." not in name:
            name = "watch_image.jpg"
        name = "".join(c for c in name if c.isalnum() or c in ".-_")
        if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            name += ".jpg"
        field.save(name, ContentFile(content), save=False)
        return True, " | ".join(warnings) if warnings else None
    except Exception as e:
        warnings.append(f"Row {row_num or '?'}: Error saving image: {str(e)}")
        return False, " | ".join(warnings)


def _background_cache_images(products_to_sync):
    """
    Downloads images and attaches them to Cloudinary storage in a background thread,
    preventing HTTP gateway and Gunicorn worker timeouts.
    """
    from django.db import close_old_connections
    close_old_connections()
    
    for pk, img1, img2, img3, img4 in products_to_sync:
        try:
            close_old_connections()
            p = Product.objects.filter(pk=pk).first()
            if not p:
                continue
            changed = False
            if img1 and not p.image:
                ok, _ = _upload_image_from_url(img1, p.image, p.name)
                if ok:
                    changed = True
            if img2 and not p.image2:
                ok, _ = _upload_image_from_url(img2, p.image2, p.name)
                if ok:
                    changed = True
            if img3 and not p.image3:
                ok, _ = _upload_image_from_url(img3, p.image3, p.name)
                if ok:
                    changed = True
            if img4 and not p.image4:
                ok, _ = _upload_image_from_url(img4, p.image4, p.name)
                if ok:
                    changed = True
            if changed:
                p.save(update_fields=["image", "image2", "image3", "image4"])
        except Exception:
            pass
        finally:
            close_old_connections()


def _is_valid_barcode(code):
    if not code:
        return False
    s = str(code).strip()
    if "e+" in s.lower() or "e-" in s.lower() or s.lower() in ["-", "n/a", "none", "null", "not found"]:
        return False
    digits_only = re.sub(r"\D", "", s)
    return len(digits_only) >= 6


@staff_member_required
def download_import_template(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="product_import_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        "ean_code", "model_number", "brand", "sub_brand", "category",
        "mrp", "price", "stock", "description", "colour", "collection",
        "movement", "warranty_period", "glass_material", "strap_material",
        "strap_color", "dial_color", "case_material", "case_size",
        "gender", "features", "image_url", "image_url2", "image_url3", "image_url4", "gst_percent", "hsn_code", "min_qty"
    ])
    writer.writerow([
        "", "EQB-1000D-1A", "Casio", "Edifice", "Wrist Watch",
        "15995", "15995", "10", "A hand-finished chronograph watch.", "Black", "Edifice",
        "Quartz", "2 Years", "Mineral Glass", "Stainless Steel",
        "Black", "Black", "Stainless Steel", "43mm",
        "Men", "Chronograph, Tachymeter", "https://images.unsplash.com/photo-1547996160-81dfa63595aa?w=1600&q=85&auto=format", "", "", "", "18", "9101", "1"
    ])
    return response
 
 
@staff_member_required
def product_bulk_import(request):
    created_count = 0
    updated_count = 0
    merged_count = 0
    errors = []
    warnings = []
    products_to_sync = []
    
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        if not csv_file:
            errors.append("No file was uploaded.")
        elif not csv_file.name.endswith(".csv"):
            errors.append("Uploaded file is not a CSV file.")
        else:
            try:
                raw_bytes = csv_file.read()
                try:
                    data_set = raw_bytes.decode("utf-8-sig")
                except UnicodeDecodeError:
                    data_set = raw_bytes.decode("latin-1")
                io_string = io.StringIO(data_set)
                reader = csv.DictReader(io_string)
                
                if not reader.fieldnames:
                    errors.append("The CSV file has no headers.")
                else:
                    # 1. Pre-fetch existing catalog and brands into memory for ultra-fast matching
                    existing_products = list(Product.objects.all())
                    
                    by_ref = {}
                    by_model = {}
                    by_brand_and_model = {}
                    by_ean = {}
                    by_name = {}
                    
                    max_numeric_ref = 0
                    for p in existing_products:
                        if p.ref:
                            ref_str = p.ref.strip().lower()
                            by_ref[ref_str] = p
                            if p.ref.isdigit():
                                max_numeric_ref = max(max_numeric_ref, int(p.ref))
                        if p.model_number:
                            m_norm = p.model_number.strip().lower()
                            by_model[m_norm] = p
                            if p.brand_id:
                                by_brand_and_model[(p.brand_id, m_norm)] = p
                        if _is_valid_barcode(p.ean_code):
                            by_ean[p.ean_code.strip().lower()] = p
                        if p.name:
                            by_name[p.name.strip().lower()] = p
                    
                    curr_ref_counter = max_numeric_ref + 1
                    
                    # Pre-load Brands and SubBrands into cache
                    brands_cache = {b.name.strip().lower(): b for b in Brand.objects.all()}
                    sub_brands_cache = {(sb.brand_id, sb.name.strip().lower()): sb for sb in SubBrand.objects.all()}

                    # Pre-resolve all brands/sub-brands from the CSV rows BEFORE the atomic block.
                    # get_or_create inside an atomic block creates a savepoint; if ANY subsequent
                    # operation in that block raises, the entire transaction is killed and Django
                    # returns a 500 Internal Server Error instead of gracefully catching the error.
                    all_rows = list(reader)  # Read all rows into memory first
                    for _row in all_rows:
                        _brand_name = (_row.get("brand") or "").strip()
                        if _brand_name:
                            _b_key = _brand_name[:60].strip().lower()
                            if _b_key not in brands_cache:
                                _brand_obj, _ = Brand.objects.get_or_create(name=_brand_name[:60].strip())
                                brands_cache[_b_key] = _brand_obj
                        _sub_brand_name = (_row.get("sub_brand") or "").strip()
                        _brand_obj_pre = brands_cache.get(_brand_name[:60].strip().lower() if _brand_name else "")
                        if _sub_brand_name and _brand_obj_pre:
                            _sb_key = (_brand_obj_pre.pk, _sub_brand_name[:60].strip().lower())
                            if _sb_key not in sub_brands_cache:
                                _sb_obj, _ = SubBrand.objects.get_or_create(
                                    brand=_brand_obj_pre,
                                    name=_sub_brand_name[:60].strip()
                                )
                                sub_brands_cache[_sb_key] = _sb_obj
                    
                    # Track products touched in THIS import session to detect intra-CSV duplicates
                    touched_in_csv = set()

                    def _clean_img_url(url_val):
                        if not url_val:
                            return ""
                        u = url_val.strip()
                        if u.upper() in ["NOT FOUND", "N/A", "NONE", "-"]:
                            return ""
                        return u

                    with transaction.atomic():
                        for i, row in enumerate(all_rows, start=2):
                            try:
                                row_ref = (row.get("ref") or row.get("Ref") or row.get("Product ID") or "").strip()
                                model_val = (row.get("model_number") or row.get("Model") or row.get("model") or row.get("SKU") or row.get("sku") or "").strip()[:100]
                                ean_val = (row.get("ean_code") or row.get("ean") or row.get("EAN") or row.get("barcode") or "").strip()[:50]
                                name_val = (row.get("name") or row.get("Name") or row.get("product_name") or row.get("Title") or "").strip()[:255]
                                
                                # Resolve Brand from pre-populated cache
                                brand_name = (row.get("brand") or "").strip()
                                brand_obj = brands_cache.get(brand_name[:60].strip().lower()) if brand_name else None
                                
                                # Resolve SubBrand from pre-populated cache
                                sub_brand_name = (row.get("sub_brand") or "").strip()
                                sub_brand_obj = None
                                if sub_brand_name and brand_obj:
                                    sub_brand_obj = sub_brands_cache.get((brand_obj.pk, sub_brand_name[:60].strip().lower()))

                                # Multi-tier deduplication matching
                                product = None
                                
                                # Tier 1: Matching by ref
                                if row_ref and row_ref.lower() in by_ref:
                                    product = by_ref[row_ref.lower()]
                                    
                                # Tier 2: Matching by model_number
                                elif model_val:
                                    m_key = model_val.strip().lower()
                                    if brand_obj and (brand_obj.pk, m_key) in by_brand_and_model:
                                        product = by_brand_and_model[(brand_obj.pk, m_key)]
                                    elif m_key in by_model:
                                        product = by_model[m_key]
                                
                                # Tier 3: Matching by valid EAN barcode
                                elif _is_valid_barcode(ean_val) and ean_val.strip().lower() in by_ean:
                                    product = by_ean[ean_val.strip().lower()]
                                    
                                # Tier 4: Matching by product name
                                elif name_val and name_val.strip().lower() in by_name:
                                    product = by_name[name_val.strip().lower()]

                                # Category parsing
                                category_raw = (row.get("category") or "").strip().lower()
                                category = Product.Category.WRIST_WATCH
                                for choice_val, choice_label in Product.Category.choices:
                                    if category_raw == choice_val.lower():
                                        category = choice_val
                                        break

                                # Pricing & stock parsing
                                try:
                                    mrp = Decimal((row.get("mrp") or "0").strip() or "0")
                                except Exception:
                                    mrp = Decimal("0")
                                    
                                try:
                                    price = Decimal((row.get("price") or "0").strip() or "0")
                                except Exception:
                                    price = Decimal("0")
                                    
                                if price == 0 and mrp > 0:
                                    price = mrp
                                    
                                try:
                                    stock = int((row.get("stock") or "5").strip() or "5")
                                except Exception:
                                    stock = 5
                                    
                                try:
                                    min_qty = int((row.get("min_qty") or "1").strip() or "1")
                                except Exception:
                                    min_qty = 1
                                    
                                gst_percent = (row.get("gst_percent") or "18").strip()
                                if gst_percent not in [choice[0] for choice in Product.GST.choices]:
                                    gst_percent = Product.GST.EIGHTEEN

                                is_new = False
                                if product is None:
                                    is_new = True
                                    if row_ref:
                                        new_ref = row_ref[:50]
                                    else:
                                        while str(curr_ref_counter).lower() in by_ref:
                                            curr_ref_counter += 1
                                        new_ref = str(curr_ref_counter)
                                        curr_ref_counter += 1
                                    # Set required fields with safe defaults on new instances
                                    # so product.save() never hits a NOT NULL constraint error
                                    product = Product(
                                        ref=new_ref,
                                        category=category,
                                        price=mrp if mrp > 0 else price,
                                        mrp=mrp,
                                    )
                                else:
                                    if product.pk and product.pk in touched_in_csv:
                                        merged_count += 1
                                    else:
                                        updated_count += 1

                                colour_val = (row.get("colour") or row.get("color") or row.get("Colour") or row.get("Color") or "").strip()[:120]

                                if name_val:
                                    product.name = name_val
                                elif is_new and not product.name:
                                    product.name = f"Product {product.ref}"

                                product.category = category
                                if _is_valid_barcode(ean_val):
                                    product.ean_code = ean_val
                                if model_val:
                                    product.model_number = model_val
                                if row.get("tts_model"):
                                    product.tts_model = row.get("tts_model").strip()[:100]
                                if brand_obj:
                                    product.brand = brand_obj
                                if sub_brand_obj:
                                    product.sub_brand = sub_brand_obj
                                if row.get("product_type"):
                                    product.product_type = row.get("product_type").strip()[:100]
                                if colour_val:
                                    product.colour = colour_val
                                if row.get("collection"):
                                    product.collection = row.get("collection").strip()[:100]
                                if row.get("warranty_period"):
                                    product.warranty_period = row.get("warranty_period").strip()[:120]
                                if row.get("glass_material"):
                                    product.glass_material = row.get("glass_material").strip()[:120]
                                if row.get("strap_material"):
                                    product.strap_material = row.get("strap_material").strip()[:120]
                                if row.get("movement"):
                                    product.movement = row.get("movement").strip()[:120]
                                if row.get("strap_color"):
                                    product.strap_color = row.get("strap_color").strip()[:120]
                                if row.get("dial_color"):
                                    product.dial_color = row.get("dial_color").strip()[:120]
                                if row.get("case_material"):
                                    product.case_material = row.get("case_material").strip()[:120]
                                if row.get("case_size"):
                                    product.case_size = row.get("case_size").strip()[:160]

                                gender_val = (row.get("gender") or row.get("Gender") or "").strip().lower()
                                if gender_val in ["men", "man", "male"]:
                                    product.gender = "Men"
                                elif gender_val in ["women", "woman", "female", "ladies"]:
                                    product.gender = "Women"
                                elif gender_val:
                                    product.gender = "Unisex"

                                if row.get("features"):
                                    product.features = row.get("features").strip()
                                if mrp > 0:
                                    product.mrp = mrp
                                if price > 0:
                                    product.price = price
                                product.gst_percent = gst_percent
                                if row.get("hsn_code"):
                                    product.hsn_code = row.get("hsn_code").strip()
                                product.min_qty = min_qty
                                if row.get("description"):
                                    product.description = row.get("description").strip()
                                if row.get("remark"):
                                    product.remark = row.get("remark").strip()

                                image_url = _clean_img_url(row.get("image_url"))
                                if image_url:
                                    product.image_url = upgrade_image_url(image_url)
                                    if "encrypted-tbn0.gstatic.com" in image_url:
                                        warnings.append(
                                            f"Row {i} ({product.name}): Google thumbnail preview URL detected. "
                                            f"Google thumbnails are low resolution (~300px). For best quality, use direct retailer or brand product image URLs."
                                        )

                                image_url2 = _clean_img_url(row.get("image_url2"))
                                if image_url2:
                                    product.image_url2 = upgrade_image_url(image_url2)

                                image_url3 = _clean_img_url(row.get("image_url3"))
                                if image_url3:
                                    product.image_url3 = upgrade_image_url(image_url3)

                                image_url4 = _clean_img_url(row.get("image_url4"))
                                if image_url4:
                                    product.image_url4 = upgrade_image_url(image_url4)

                                product.stock = stock

                                featured_val = (row.get("featured") or "").strip().lower()
                                if featured_val:
                                    product.featured = featured_val in ["true", "yes", "1", "t"]

                                product.save()

                                if is_new:
                                    created_count += 1

                                if product.pk:
                                    touched_in_csv.add(product.pk)
                                by_ref[product.ref.strip().lower()] = product
                                if product.model_number:
                                    m_norm = product.model_number.strip().lower()
                                    by_model[m_norm] = product
                                    if product.brand_id:
                                        by_brand_and_model[(product.brand_id, m_norm)] = product
                                if _is_valid_barcode(product.ean_code):
                                    by_ean[product.ean_code.strip().lower()] = product
                                if product.name:
                                    by_name[product.name.strip().lower()] = product

                                if product.image_url or product.image_url2 or product.image_url3 or product.image_url4:
                                    products_to_sync.append((
                                        product.pk,
                                        product.image_url,
                                        product.image_url2,
                                        product.image_url3,
                                        product.image_url4,
                                    ))

                            except Exception as row_err:
                                errors.append(f"Row {i} (model: {row.get('model_number') or row.get('Model') or ''}): {str(row_err)}")

            except Exception as e:
                errors.append(f"Fatal error parsing CSV: {str(e)}")
                
        if created_count > 0 or updated_count > 0 or merged_count > 0:
            if products_to_sync:
                threading.Thread(
                    target=_background_cache_images,
                    args=(products_to_sync,),
                    daemon=True
                ).start()
                
            parts = []
            if created_count > 0:
                parts.append(f"{created_count} products added")
            if updated_count > 0:
                parts.append(f"{updated_count} products updated")
            if merged_count > 0:
                parts.append(f"{merged_count} duplicate CSV rows merged")
            msg = f"Import complete: {', '.join(parts)}."

            if errors:
                messages.warning(request, f"{msg} (Note: {len(errors)} row error(s) flagged below).")
            elif warnings:
                messages.warning(request, f"{msg} (Note: {len(warnings)} image quality warning(s) flagged below).")
            else:
                messages.success(request, msg)
                return redirect("product_manage_list")
            
    return render(request, "store/product_import.html", {
        "created_count": created_count,
        "updated_count": updated_count,
        "merged_count": merged_count,
        "errors": errors,
        "warnings": warnings,
    })
