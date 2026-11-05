"""Doimiy buyurtmalardan oddiy buyurtmalar yaratish.

Ham `python manage.py create_recurring_orders` buyrug'i, ham boshliq panelidagi
"Bugungi buyurtmalarni yaratish" tugmasi shu funksiyadan foydalanadi.
Takror ishga tushirilsa ham bir kunga ikkinchi buyurtma yaratilmaydi
(bazada `recurring + delivery_date` takrorlanmas).
"""

from django.db import IntegrityError

from .models import Order, RecurringOrder
from .services import create_order


def create_recurring_orders(day, user=None) -> dict:
    created, existing, skipped = [], 0, 0
    recurring_orders = (
        RecurringOrder.objects.filter(is_active=True)
        .select_related("customer", "driver")
        .prefetch_related("items__product")
    )
    for rec in recurring_orders:
        if not rec.runs_on(day):
            continue
        if Order.objects.filter(recurring=rec, delivery_date=day).exists():
            existing += 1
            continue
        items = {item.product: item.quantity for item in rec.items.all() if item.product.is_active}
        if not items:
            skipped += 1  # mahsulotlari faol emas
            continue
        driver = rec.driver if rec.driver and rec.driver.is_active else None
        try:
            order = create_order(
                customer=rec.customer,
                items=items,
                delivery_date=day,
                driver=driver,
                note=rec.note,
                user=user,
                recurring=rec,
            )
        except IntegrityError:
            existing += 1  # shu paytda boshqa jarayon yaratib ulgurdi
            continue
        created.append(order)
    return {"created": created, "existing": existing, "skipped": skipped}
