"""Har bir shablonga avtomatik uzatiladigan qiymatlar."""

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from customers.models import BottlePickup
from orders.models import Order

# Boshliq menyusi: (nomi, Bootstrap ikonka, URL nomi, qaysi sahifalarda "faol" ko'rinadi)
BOSS_MENU = [
    ("Bosh sahifa", "bi-grid", "reports:dashboard", ("reports:dashboard",)),
    ("Buyurtmalar", "bi-box-seam", "orders:list", ("orders:list", "orders:create", "orders:detail", "orders:edit")),
    ("Doimiy buyurtmalar", "bi-arrow-repeat", "orders:recurring_list", ("orders:recurring",)),
    (
        "Mijozlar",
        "bi-people",
        "customers:list",
        ("customers:list", "customers:create", "customers:detail", "customers:edit", "customers:payment"),
    ),
    ("Qarzdorlar", "bi-wallet2", "customers:debtors", ("customers:debtors",)),
    ("Butillar", "bi-droplet", "customers:bottles", ("customers:bottle", "customers:pickup")),
    ("Ombor", "bi-boxes", "inventory:stock", ("inventory:stock",)),
    ("Mahsulotlar", "bi-tag", "inventory:product_list", ("inventory:product",)),
    ("Yetkazuvchilar", "bi-truck", "accounts:driver_list", ("accounts:driver",)),
    ("Hisobotlar", "bi-bar-chart", "reports:report", ("reports:report", "reports:export")),
]


def site(request):
    # Shablonlarda {{ SITE_NAME }} deb ishlatiladi
    return {"SITE_NAME": settings.SITE_NAME}


def navigation(request):
    """Menyu: boshliq uchun bandlar ro'yxati, yetkazuvchi uchun qolgan buyurtmalar soni."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    if user.is_driver:
        today = timezone.localdate()
        remaining = Order.objects.filter(driver=user, status__in=Order.OPEN_STATUSES, delivery_date__lte=today).count()
        # Butil olib kelish topshiriqlari ham qolgan ishlar qatoriga kiradi
        remaining += BottlePickup.objects.filter(driver=user, status=BottlePickup.Status.PLANNED, date__lte=today).count()
        return {"driver_remaining": remaining}
    if not user.is_boss:
        return {}
    match = getattr(request, "resolver_match", None)
    current = match.view_name if match else ""
    menu = [
        {
            "label": label,
            "icon": icon,
            "url": reverse(url_name),
            "active": any(current.startswith(prefix) for prefix in prefixes),
        }
        for label, icon, url_name, prefixes in BOSS_MENU
    ]
    return {"boss_menu": menu}
