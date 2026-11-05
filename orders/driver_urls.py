"""Yetkazuvchi paneli manzillari: /driver/..."""

from django.urls import path

from . import driver_views as views

app_name = "driver"

urlpatterns = [
    path("", views.today, name="today"),
    path("my-day/", views.my_day, name="my_day"),
    path("orders/<int:pk>/start/", views.start, name="start"),
    path("orders/<int:pk>/deliver/", views.deliver, name="deliver"),
    path("orders/<int:pk>/fail/", views.fail, name="fail"),
    path("pickups/<int:pk>/done/", views.pickup_done, name="pickup_done"),
    path("pickups/<int:pk>/fail/", views.pickup_fail, name="pickup_fail"),
]
