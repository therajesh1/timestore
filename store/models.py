from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Brand(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    logo = models.ImageField(upload_to="brands/", blank=True, null=True)
    logo_static = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Path under static/, e.g. images/brands/casio.webp (used if no logo upload)",
    )
    show_in_nav = models.BooleanField(default=True, help_text="Show in the site navbar brand strip")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def display_logo(self):
        if self.logo:
            return self.logo.url
        return None


class SubBrand(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="sub_brands")
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["brand__name", "name"]
        unique_together = ("brand", "name")

    def __str__(self):
        return f"{self.brand.name} · {self.name}"


class Product(models.Model):
    class Category(models.TextChoices):
        WRIST_WATCH = "Wrist Watch", "Wrist Watch"
        WALL_CLOCKS = "Wall Clocks", "Wall Clocks"
        PERFUMES = "Perfumes", "Perfumes"
        ACCESSORIES = "Accessories", "Accessories"
        SMART_WATCHS = "Smart Watchs", "Smart Watchs"
        KIDS = "Kids Watch", "Kids Watch"

    class GST(models.TextChoices):
        ZERO = "0", "0%"
        FIVE = "5", "5%"
        TWELVE = "12", "12%"
        EIGHTEEN = "18", "18%"
        TWENTYEIGHT = "28", "28%"

    # Product Master
    ean_code = models.CharField("EAN code", max_length=13, blank=True, default="")
    name = models.CharField("Product name", max_length=120)
    ref = models.CharField("Product ID / ref. code", max_length=20, unique=True)
    model_number = models.CharField("Model", max_length=50, blank=True, default="")
    tts_model = models.CharField("TTS model", max_length=50, blank=True, default="")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    sub_brand = models.ForeignKey(SubBrand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    category = models.CharField("Category", max_length=30, choices=Category.choices)
    product_type = models.CharField("Type", max_length=50, blank=True, default="")
    colour = models.CharField(max_length=30, blank=True, default="")
    collection = models.CharField(max_length=50, blank=True, default="")

    # Specifications
    warranty_period = models.CharField("Warranty Period", max_length=120, blank=True, default="")
    glass_material = models.CharField("Glass Material", max_length=120, blank=True, default="")
    strap_material = models.CharField("Strap Material", max_length=120, blank=True, default="")
    movement = models.CharField("Movement", max_length=120, blank=True, default="")
    strap_color = models.CharField("Strap Color", max_length=120, blank=True, default="")
    dial_color = models.CharField("Dial Color", max_length=120, blank=True, default="")
    case_material = models.CharField("Case Material", max_length=120, blank=True, default="")
    case_size = models.CharField("Case Size", max_length=80, blank=True, default="")
    gender = models.CharField(
        "Gender",
        max_length=20,
        choices=[("Men", "Men"), ("Women", "Women"), ("Unisex", "Unisex")],
        default="Unisex"
    )
    features = models.TextField("Features", blank=True, default="", help_text="e.g. fragrance notes, key highlights")

    # Pricing & tax
    mrp = models.DecimalField("MRP", max_digits=12, decimal_places=2, default=0, help_text="Maximum retail price, in INR")
    price = models.DecimalField("Selling price", max_digits=12, decimal_places=2, help_text="Price in INR")
    gst_percent = models.CharField("GST %", max_length=3, choices=GST.choices, default=GST.EIGHTEEN)
    hsn_code = models.CharField("HSN", max_length=10, blank=True, default="9101")
    min_qty = models.PositiveIntegerField("Min qty", default=1)

    description = models.TextField(blank=True, default="")
    remark = models.TextField(blank=True, default="")
    image = models.ImageField("Picture", upload_to="products/", blank=True, null=True)
    image_url = models.URLField("Picture URL (fallback)", max_length=500, blank=True)
    image2 = models.ImageField("Picture 2", upload_to="products/", blank=True, null=True)
    image3 = models.ImageField("Picture 3", upload_to="products/", blank=True, null=True)
    image4 = models.ImageField("Picture 4", upload_to="products/", blank=True, null=True)
    stock = models.PositiveIntegerField(default=5)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} · {self.name}"

    def get_absolute_url(self):
        return reverse("product_detail", args=[self.pk])

    def formatted_price(self):
        return f"₹{self.price:,.0f}"

    def formatted_mrp(self):
        return f"₹{self.mrp:,.0f}"

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        return self.image_url

    @property
    def all_images(self):
        imgs = []
        if self.image:
            imgs.append(self.image.url)
        elif self.image_url:
            imgs.append(self.image_url)
        if self.image2:
            imgs.append(self.image2.url)
        if self.image3:
            imgs.append(self.image3.url)
        if self.image4:
            imgs.append(self.image4.url)
        return imgs


class Order(models.Model):
    class Status(models.TextChoices):
        PLACED = "Placed", "Placed"
        CONFIRMED = "Confirmed", "Confirmed"
        SHIPPED = "Shipped", "Shipped"
        DELIVERED = "Delivered", "Delivered"
        CANCELLED = "Cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PLACED)
    shipping_address = models.TextField()
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} · {self.user}"

    def formatted_total(self):
        return f"₹{self.total:,.0f}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Unit price at time of purchase")

    def line_total(self):
        return self.price * self.quantity

    def formatted_line_total(self):
        return f"₹{self.line_total():,.0f}"


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"Profile · {self.user}"
