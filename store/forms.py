from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Brand, Order, Product, ProductColor, SubBrand


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Shipping address")


class ProductForm(forms.ModelForm):
    # Fields kept when instantiated with simple=True (Wall Clocks / Perfumes / Accessories).
    # Every field NOT in this set is deleted from the form so it's left untouched on
    # save (rather than being explicitly cleared, which would happen if it stayed in
    # the form as an empty, unrendered field).
    SIMPLE_FIELDS = {"ref", "name", "description", "price", "category", "features", "image", "image_url", "image2", "image3", "image4"}

    class Meta:
        model = Product
        fields = [
            "ref", "ean_code", "name", "model_number", "tts_model",
            "brand", "sub_brand", "category", "product_type", "colour", "collection",
            "description",
            "image", "image_url", "image2", "image3", "image4",
            "mrp", "price", "gst_percent", "hsn_code", "min_qty",
            "stock", "featured", "remark",
            "warranty_period", "glass_material", "strap_material",
            "movement", "strap_color", "dial_color", "case_material", "features",
            "gender", "case_size",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "remark": forms.Textarea(attrs={"rows": 3}),
            "features": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, simple=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ref"].disabled = True
        self.fields["ref"].required = False
        self.fields["ref"].help_text = "Auto-generated from the product count."
        if simple:
            for name in list(self.fields):
                if name not in self.SIMPLE_FIELDS:
                    del self.fields[name]


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "logo", "logo_static", "show_in_nav", "order", "banner", "banner_mobile"]


class SubBrandForm(forms.ModelForm):
    class Meta:
        model = SubBrand
        fields = ["brand", "name", "logo"]


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status"]


ProductColorFormSet = forms.inlineformset_factory(
    Product,
    ProductColor,
    fields=("color_name", "image1", "image2", "image3", "image4"),
    extra=0,
    can_delete=True,
)
