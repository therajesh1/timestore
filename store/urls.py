from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:pk>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_history, name="order_history"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/products/", views.product_manage_list, name="product_manage_list"),
    path("dashboard/products/add/", views.product_create, name="product_create"),
    path("dashboard/products/import/", views.product_bulk_import, name="product_bulk_import"),
    path("dashboard/products/import/template/", views.download_import_template, name="download_import_template"),
    path("dashboard/products/<int:pk>/edit/", views.product_update, name="product_update"),
    path("dashboard/products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    path("dashboard/brands/", views.brand_manage_list, name="brand_manage_list"),
    path("dashboard/brands/<int:pk>/", views.brand_detail, name="brand_detail"),
    path("dashboard/subbrands/<int:pk>/delete/", views.subbrand_delete, name="subbrand_delete"),
    path("dashboard/orders/", views.order_manage_list, name="order_manage_list"),
    path("dashboard/orders/<int:pk>/", views.order_manage_detail, name="order_manage_detail"),
    path("accounts/register/", views.register, name="register"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
]
