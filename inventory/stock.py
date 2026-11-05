"""Ombor qoldig'ini hisoblash.

Qoldiq = jami ishlab chiqarilgan − jami yetkazilgan (holati "yetkazildi" bo'lgan
buyurtmalardagi mahsulotlar). Yakunlanmagan buyurtmalardagi miqdor alohida
ko'rsatiladi: bu mahsulot hali ombordan chiqmagan, lekin unga talab bor.
"""

from django.db.models import Sum
from django.db.models.functions import Coalesce

from orders.models import Order, OrderItem

from .models import Product, StockEntry


def _sum_by_product(queryset, field="quantity") -> dict[int, int]:
    """{mahsulot_id: jami_soni} lug'ati."""
    rows = queryset.values("product").annotate(total=Sum(field))
    return {row["product"]: row["total"] for row in rows}


def stock_summary(today) -> list[dict]:
    products = Product.objects.annotate(produced=Coalesce(Sum("stock_entries__quantity"), 0))
    delivered = _sum_by_product(OrderItem.objects.filter(order__status=Order.Status.DELIVERED))
    pending = _sum_by_product(OrderItem.objects.filter(order__status__in=Order.OPEN_STATUSES))
    produced_today = _sum_by_product(StockEntry.objects.filter(date=today))

    rows = []
    for product in products:
        row = {
            "product": product,
            "produced": product.produced,
            "produced_today": produced_today.get(product.pk, 0),
            "delivered": delivered.get(product.pk, 0),
            "pending": pending.get(product.pk, 0),
        }
        row["remaining"] = row["produced"] - row["delivered"]
        # Faol bo'lmagan va hech qanday harakati yo'q mahsulotni ko'rsatmaymiz
        if product.is_active or row["produced"] or row["delivered"]:
            rows.append(row)
    return rows
