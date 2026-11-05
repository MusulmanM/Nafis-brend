from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("new/", views.customer_create, name="create"),
    path("lookup/", views.customer_lookup, name="lookup"),
    path("debtors/", views.debtors, name="debtors"),
    path("bottles/", views.bottles, name="bottles"),
    path("pickups/<int:pk>/cancel/", views.pickup_cancel, name="pickup_cancel"),
    path("<int:pk>/", views.customer_detail, name="detail"),
    path("<int:pk>/edit/", views.customer_edit, name="edit"),
    path("<int:pk>/payment/", views.customer_payment, name="payment"),
    path("<int:pk>/bottles/return/", views.bottle_return, name="bottle_return"),
    path("<int:pk>/bottles/pickup/", views.pickup_create, name="pickup_create"),
]
