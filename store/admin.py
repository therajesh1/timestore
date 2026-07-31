from django.contrib import admin

from .models import Brand, Order, OrderItem, Product, Profile, SubBrand


class SubBrandInline(admin.TabularInline):
    model = SubBrand
    extra = 1


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "show_in_nav", "order", "sub_brand_count")
    list_editable = ("show_in_nav", "order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SubBrandInline]

    def sub_brand_count(self, obj):
        return obj.sub_brands.count()

    sub_brand_count.short_description = "Sub-brands"


@admin.register(SubBrand)
class SubBrandAdmin(admin.ModelAdmin):
    list_display = ("name", "brand")
    list_filter = ("brand",)
    search_fields = ("name", "brand__name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("ref", "name", "brand", "category", "mrp", "price", "stock", "featured", "created_at")
    list_filter = ("brand", "category", "gst_percent", "featured")
    search_fields = ("name", "ref", "ean_code", "model_number", "tts_model", "tagline", "brand__name")
    list_editable = ("price", "stock", "featured")
    autocomplete_fields = ("brand", "sub_brand")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    fieldsets = (
        ("Product Details", {
            "fields": (
                ("ref", "created_at"),
                "ean_code",
                "name",
                ("model_number", "tts_model"),
                ("brand", "sub_brand"),
                ("category", "product_type"),
                ("colour", "collection"),
                "tagline",
                ("image", "image_url"),
            ),
        }),
        ("Pricing & Tax", {
            "fields": (
                ("mrp", "price"),
                ("gst_percent", "hsn_code"),
                "min_qty",
            ),
        }),
        ("Inventory & Notes", {
            "fields": ("stock", "featured", "description", "remark"),
        }),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "user__email", "id")
    list_editable = ("status",)
    inlines = [OrderItemInline]
    readonly_fields = ("user", "total", "shipping_address", "created_at")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__username", "phone")
