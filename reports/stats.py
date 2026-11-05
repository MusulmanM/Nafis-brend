"""
Statistika hisob-kitoblari (dashboard, yetkazuvchilar, keyinchalik hisobotlar).

Sanalar bo'yicha qoida:
  * buyurtmalar SONI — buyurtmaning "yetkazish sanasi" (delivery_date) bo'yicha;
  * PUL (tushum) — haqiqatda yetkazilgan vaqti (delivered_at) va qarz to'lovlari
    sanasi bo'yicha, ya'ni pul aynan qaysi kuni olingan bo'lsa, o'sha kunga yoziladi.
"""

from datetime import date, timedelta

from django.db.models import Count, F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncDate

from accounts.models import User
from core.choices import PAYMENT_METHOD_CHOICES, PaymentType
from customers.models import BottlePickup, Customer, Payment
from orders.models import WEEKDAY_SHORT, Order, OrderItem

DELIVERED = Order.Status.DELIVERED


def date_q(field: str, start: date | None, end: date | None) -> Q:
    """Sana oralig'i uchun filtr. start/end bo'sh bo'lsa, cheklanmaydi."""
    q = Q()
    if start:
        q &= Q(**{f"{field}__gte": start})
    if end:
        q &= Q(**{f"{field}__lte": end})
    return q


def order_counts(orders: QuerySet) -> dict:
    """Buyurtmalar soni holatlar bo'yicha (bekor qilinganlar hisobga olinmaydi)."""
    return orders.exclude(status=Order.Status.CANCELLED).aggregate(
        total=Count("id"),
        delivered=Count("id", filter=Q(status=DELIVERED)),
        pending=Count("id", filter=Q(status__in=Order.OPEN_STATUSES)),
        failed=Count("id", filter=Q(status=Order.Status.FAILED)),
    )


def collected_money(orders: QuerySet, start: date | None, end: date | None) -> dict:
    """Yetkazilgan buyurtmalardan olingan pul: jami va naqd."""
    delivered = orders.filter(Q(status=DELIVERED) & date_q("delivered_at__date", start, end))
    return delivered.aggregate(
        count=Count("id"),
        total=Coalesce(Sum("paid_amount"), 0),
        cash=Coalesce(Sum("paid_amount", filter=Q(payment_type=PaymentType.CASH)), 0),
        bottles_returned=Coalesce(Sum("returned_bottles"), 0),
    )


def revenue_by_day(start: date, end: date) -> list[tuple[date, int]]:
    """Har bir kun uchun tushum: buyurtmalardan olingan pul + qarz to'lovlari."""
    totals = {start + timedelta(days=i): 0 for i in range((end - start).days + 1)}

    order_rows = (
        Order.objects.filter(Q(status=DELIVERED) & date_q("delivered_at__date", start, end))
        .annotate(day=TruncDate("delivered_at"))
        .values("day")
        .annotate(amount=Sum("paid_amount"))
    )
    for row in order_rows:
        totals[row["day"]] += row["amount"] or 0

    payment_rows = Payment.objects.filter(date__range=(start, end)).values("date").annotate(amount=Sum("amount"))
    for row in payment_rows:
        totals[row["date"]] += row["amount"] or 0

    return list(totals.items())


def picked_bottles(pickups: QuerySet) -> int:
    """Buyurtmasiz (alohida) olib kelingan butillar soni."""
    return pickups.filter(status=BottlePickup.Status.DONE).aggregate(s=Coalesce(Sum("quantity"), 0))["s"]


def driver_stats(driver, start: date | None, end: date | None) -> dict:
    """Bitta yetkazuvchining tanlangan davrdagi ko'rsatkichlari."""
    orders = Order.objects.filter(driver=driver)
    counts = order_counts(orders.filter(date_q("delivery_date", start, end)))
    money = collected_money(orders, start, end)
    # Qaytgan butillar = yetkazishda olinganlar + alohida olib kelinganlar
    picked = picked_bottles(BottlePickup.objects.filter(Q(driver=driver) & date_q("date", start, end)))
    return {
        **counts,
        "collected": money["total"],
        "cash": money["cash"],
        "bottles_returned": money["bottles_returned"] + picked,
    }


# --- Hisobot (istalgan sana oralig'i uchun) -----------------------------------

MONTHS = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]


def chart_series(daily: list[tuple[date, int]]) -> dict:
    """Grafik uchun yozuvlar. Uzun davrda kunlar oylarga birlashtiriladi."""
    if len(daily) <= 62:
        if len(daily) <= 31:
            labels = [[WEEKDAY_SHORT[d.weekday()], f"{d:%d.%m}"] for d, _ in daily]
        else:
            labels = [f"{d:%d.%m}" for d, _ in daily]
        return {"labels": labels, "values": [v for _, v in daily]}
    months: dict[tuple[int, int], int] = {}
    for d, value in daily:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + value
    return {
        "labels": [f"{MONTHS[m - 1]} {y}" for (y, m) in months],
        "values": list(months.values()),
    }


def build_report(start: date, end: date) -> dict:
    """Hisobot uchun barcha ko'rsatkichlar (sahifa ham, Excel ham shundan foydalanadi)."""
    scheduled = Order.objects.filter(delivery_date__range=(start, end))
    delivered = Order.objects.filter(status=DELIVERED, delivered_at__date__range=(start, end))
    payments = Payment.objects.filter(date__range=(start, end))

    counts = scheduled.aggregate(
        total=Count("id", filter=~Q(status=Order.Status.CANCELLED)),
        delivered=Count("id", filter=Q(status=DELIVERED)),
        failed=Count("id", filter=Q(status=Order.Status.FAILED)),
        cancelled=Count("id", filter=Q(status=Order.Status.CANCELLED)),
        pending=Count("id", filter=Q(status__in=Order.OPEN_STATUSES)),
    )

    money = delivered.aggregate(
        sales=Coalesce(Sum("total_amount"), 0),
        collected=Coalesce(Sum("paid_amount"), 0),
        new_debt=Coalesce(Sum(F("total_amount") - F("paid_amount"), filter=Q(total_amount__gt=F("paid_amount"))), 0),
        bottles_given=Coalesce(Sum("bottles_given"), 0),
        bottles_returned=Coalesce(Sum("returned_bottles"), 0),
    )
    # Buyurtmasiz olib kelingan butillar ham "qaytarilgan" hisobiga qo'shiladi
    pickups = BottlePickup.objects.filter(status=BottlePickup.Status.DONE, date__range=(start, end))
    money["bottles_picked"] = picked_bottles(pickups)
    money["bottles_returned"] += money["bottles_picked"]
    money["debt_payments"] = payments.aggregate(s=Coalesce(Sum("amount"), 0))["s"]
    money["received"] = money["collected"] + money["debt_payments"]

    # To'lov turlari: buyurtmalardan + qarz to'lovlaridan
    from_orders = dict(delivered.values_list("payment_type").annotate(s=Sum("paid_amount")))
    from_payments = dict(payments.values_list("method").annotate(s=Sum("amount")))
    payment_types = []
    for value, label in PAYMENT_METHOD_CHOICES:
        a, b = from_orders.get(value) or 0, from_payments.get(value) or 0
        payment_types.append({"label": label, "orders": a, "payments": b, "total": a + b})
    payment_types.sort(key=lambda row: -row["total"])

    products = list(
        OrderItem.objects.filter(order__in=delivered)
        .values("product__name")
        .annotate(sold=Sum("quantity"), amount=Sum(F("quantity") * F("price")))
        .order_by("-sold")
    )

    driver_q = Q(orders__status=DELIVERED, orders__delivered_at__date__range=(start, end))
    # Alohida olib kelingan butillar yetkazuvchi bo'yicha (alohida so'rov — JOIN'lar
    # aralashib, yig'indilar ikki marta hisoblanmasligi uchun)
    picked_by_driver = dict(
        pickups.filter(driver__isnull=False).values("driver").annotate(s=Sum("quantity")).values_list("driver", "s")
    )
    drivers = []
    for d in (
        User.objects.filter(role=User.Role.DRIVER)
        .annotate(
            delivered=Count("orders", filter=driver_q),
            failed=Count(
                "orders", filter=Q(orders__status=Order.Status.FAILED, orders__delivery_date__range=(start, end))
            ),
            collected=Coalesce(Sum("orders__paid_amount", filter=driver_q), 0),
            cash=Coalesce(Sum("orders__paid_amount", filter=driver_q & Q(orders__payment_type=PaymentType.CASH)), 0),
            bottles_returned=Coalesce(Sum("orders__returned_bottles", filter=driver_q), 0),
        )
        .order_by("-delivered", "first_name")
    ):
        d.bottles_picked = picked_by_driver.get(d.pk, 0)
        d.bottles_returned += d.bottles_picked
        if d.delivered or d.failed or d.bottles_picked:
            drivers.append(d)

    in_range = Q(orders__delivery_date__range=(start, end)) & ~Q(orders__status=Order.Status.CANCELLED)
    top_customers = (
        Customer.objects.annotate(
            order_count=Count("orders", filter=in_range),
            amount=Coalesce(Sum("orders__total_amount", filter=in_range & Q(orders__status=DELIVERED)), 0),
        )
        .filter(order_count__gt=0)
        .order_by("-order_count", "-amount", "name")[:10]
    )

    daily = revenue_by_day(start, end)
    return {
        "start": start,
        "end": end,
        "days": (end - start).days + 1,
        "counts": counts,
        "money": money,
        "payment_types": payment_types,
        "products": products,
        "drivers": drivers,
        "top_customers": list(top_customers),
        "daily": daily,
        "chart": chart_series(daily),
        "orders": scheduled.select_related("customer", "driver").order_by("delivery_date", "pk"),
    }
