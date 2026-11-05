"""
Asosiy URL manzillar. Har bir app o'zining `urls.py` fayliga ega va shu yerga ulanadi.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# Django admin panel sarlavhalari
admin.site.site_header = f"{settings.SITE_NAME} — zaxira boshqaruv"
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = "Ma'lumotlarni boshqarish"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("panel/", include("reports.urls")),  # boshliq bosh sahifasi
    path("orders/", include("orders.urls")),
    path("customers/", include("customers.urls")),
    path("inventory/", include("inventory.urls")),
    path("driver/", include("orders.driver_urls")),  # yetkazuvchi paneli
    path("", include("accounts.urls")),  # /, /login/, /logout/, /drivers/
]
