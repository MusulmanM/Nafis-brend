from django.urls import path

from . import recurring_views, views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("new/", views.order_create, name="create"),
    path("<int:pk>/", views.order_detail, name="detail"),
    path("<int:pk>/edit/", views.order_edit, name="edit"),
    path("<int:pk>/assign/", views.order_assign, name="assign"),
    path("<int:pk>/cancel/", views.order_cancel, name="cancel"),
    # Doimiy buyurtmalar
    path("recurring/", recurring_views.recurring_list, name="recurring_list"),
    path("recurring/new/", recurring_views.recurring_create, name="recurring_create"),
    path("recurring/run/", recurring_views.recurring_run, name="recurring_run"),
    path("recurring/<int:pk>/edit/", recurring_views.recurring_edit, name="recurring_edit"),
    path("recurring/<int:pk>/delete/", recurring_views.recurring_delete, name="recurring_delete"),
]
