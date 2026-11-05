"""Boshliq bosh sahifasi (dashboard), hisobotlar va Excel eksport."""

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import boss_required
from accounts.models import User
from customers.models import BottlePickup, Customer
from orders.models import WEEKDAY_SHORT, Order

from .excel import build_workbook
from .periods import PRESETS, resolve_period
from .stats import build_report, order_counts, revenue_by_day


@boss_required
def dashboard(request):
    today = timezone.localdate()
    open_orders = Order.objects.filter(status__in=Order.OPEN_STATUSES)

    counts = order_counts(Order.objects.filter(delivery_date=today))
    overdue = open_orders.filter(delivery_date__lt=today).count()
    unassigned = open_orders.filter(driver__isnull=True, delivery_date__lte=today).count()

    week = revenue_by_day(today - timedelta(days=6), today)
    chart = {
        # Ikki qatorli yozuv: ["Du", "03.11"] — telefonda ham qiyshaymaydi
        "labels": [[WEEKDAY_SHORT[d.weekday()], f"{d:%d.%m}"] for d, _ in week],
        "values": [amount for _, amount in week],
    }

    balances = Customer.objects.aggregate(
        total_debt=Coalesce(Sum("debt"), 0),
        debtors=Count("id", filter=Q(debt__gt=0)),
        total_bottles=Coalesce(Sum("bottles"), 0),
    )
    balances["open_pickups"] = BottlePickup.objects.filter(status=BottlePickup.Status.PLANNED).count()

    # Yetkazuvchilar bugun: nechta yetkazdi, nechtasi qoldi, qancha pul yig'di
    today_q = Q(orders__delivery_date=today)
    delivered_today_q = Q(orders__status=Order.Status.DELIVERED, orders__delivered_at__date=today)
    drivers = (
        User.objects.filter(role=User.Role.DRIVER, is_active=True)
        .annotate(
            total=Count("orders", filter=today_q & ~Q(orders__status=Order.Status.CANCELLED)),
            delivered=Count("orders", filter=today_q & Q(orders__status=Order.Status.DELIVERED)),
            pending=Count("orders", filter=today_q & Q(orders__status__in=Order.OPEN_STATUSES)),
            collected=Coalesce(Sum("orders__paid_amount", filter=delivered_today_q), 0),
        )
        .order_by("-total", "first_name")
    )

    return render(
        request,
        "reports/dashboard.html",
        {
            "today": today,
            "counts": counts,
            "overdue": overdue,
            "unassigned": unassigned,
            "revenue_today": week[-1][1],
            "revenue_week": sum(amount for _, amount in week),
            "week": week,
            "chart": chart,
            "balances": balances,
            "drivers": drivers,
        },
    )


@boss_required
def report(request):
    """Hisobot: kunlik, haftalik, oylik yoki istalgan sana oralig'i uchun."""
    period, start, end, error = resolve_period(request.GET, timezone.localdate())
    if error:
        messages.error(request, error)
    data = build_report(start, end)
    return render(
        request,
        "reports/report.html",
        {
            **data,
            "period": period,
            "presets": PRESETS,
            "query": request.GET.urlencode(),
            "payment_chart": {
                "labels": [row["label"] for row in data["payment_types"]],
                "values": [row["total"] for row in data["payment_types"]],
            },
        },
    )


@boss_required
def export_excel(request):
    """Hisobotni Excel faylga yuklab olish (sahifadagi davr bilan bir xil)."""
    _, start, end, _ = resolve_period(request.GET, timezone.localdate())
    workbook = build_workbook(build_report(start, end))
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="hisobot_{start:%Y-%m-%d}_{end:%Y-%m-%d}.xlsx"'
    workbook.save(response)
    return response
