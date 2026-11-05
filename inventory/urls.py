from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.stock, name="stock"),
    path("entries/<int:pk>/delete/", views.stock_entry_delete, name="stock_entry_delete"),
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
]
