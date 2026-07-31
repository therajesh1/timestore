from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Brand, Order, Product, SubBrand


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class CheckoutForm(forms.Form):
    shipping_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), label="Shipping address")


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "ref", "ean_code", "name", "model_number", "tts_model",
            "brand", "sub_brand", "category", "product_type", "colour", "collection", "tagline",
            "image", "image_url",
            "mrp", "price", "gst_percent", "hsn_code", "min_qty",
            "stock", "featured", "description", "remark",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "remark": forms.Textarea(attrs={"rows": 3}),
        }


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "logo", "logo_static", "show_in_nav", "order"]


class SubBrandForm(forms.ModelForm):
    class Meta:
        model = SubBrand
        fields = ["name"]


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status"]
