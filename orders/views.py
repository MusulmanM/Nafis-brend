"""Boshliq uchun buyurtmalar: ro'yxat, yaratish, tahrirlash, biriktirish, bekor qilish."""

import re
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.decorators import boss_required
from core.phone import PHONE_RE, normalize_phone
from customers.models import Customer

from .forms import OrderForm, active_drivers
from .models import Order
from .services import assign_driver, cancel_order, create_order, update_order


def parse_date_param(value):
    try:
        return parse_date(value or "")
    except ValueError:  # masalan, 2026-02-31
        return None


@boss_required
def order_list(request):
    today = timezone.localdate()
    orders = Order.objects.select_related("customer", "driver")

    # --- Filtrlar ---
    text = request.GET.get("q", "").strip()
    day = parse_date_param(request.GET.get("date"))
    overdue = request.GET.get("overdue") == "1"
    status = request.GET.get("status", "")
    driver = request.GET.get("driver", "")

    if text:
        q = Q(customer__name__icontains=text) | Q(customer__address__icontains=text)
        digits = re.sub(r"\D", "", text)
        if len(digits) >= 3:
            q |= Q(customer__phone__contains=digits)
        if text.lstrip("#").isdigit():
            q |= Q(pk=int(text.lstrip("#")))
        orders = orders.filter(q)
    if day:
        orders = orders.filter(delivery_date=day)
    if overdue:
        orders = orders.filter(status__in=Order.OPEN_STATUSES, delivery_date__lt=today)
    if status in Order.Status.values:
        orders = orders.filter(status=status)
    if driver == "none":
        orders = orders.filter(driver__isnull=True)
    elif driver.isdigit():
        orders = orders.filter(driver_id=int(driver))

    totals = orders.exclude(status=Order.Status.CANCELLED).aggregate(amount=Coalesce(Sum("total_amount"), 0))
    page = Paginator(orders.order_by("-delivery_date", "-created_at"), 30).get_page(request.GET.get("page"))

    return render(
        request,
        "orders/order_list.html",
        {
            "page_obj": page,
            "totals": totals,
            "q": text,
            "day": day,
            "overdue": overdue,
            "status": status,
            "driver": driver,
            "statuses": Order.Status.choices,
            "drivers": active_drivers(),
            "today": today,
            "tomorrow": today + timedelta(days=1),
        },
    )


def _found_customer(form, initial_phone):
    """Formada telefon bo'yicha topilgan mijoz (shablonda ko'rsatish uchun)."""
    if form.is_bound:
        return form.customer
    phone = normalize_phone(initial_phone)
    if PHONE_RE.match(phone):
        return Customer.objects.filter(phone=phone).first()
    return None


@boss_required
def order_create(request):
    initial_phone = request.GET.get("phone", "")
    form = OrderForm(request.POST or None, initial={"phone": initial_phone})

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        token = data.get("token")
        try:
            with transaction.atomic():
                customer = form.customer or Customer.objects.create(**form.new_customer_data())
                order = create_order(
                    customer=customer,
                    items=form.items,
                    driver=data["driver"],
                    delivery_date=data["delivery_date"],
                    note=data["note"],
                    user=request.user,
                    client_token=token,
                )
        except IntegrityError:
            existing = Order.objects.filter(client_token=token).first() if token else None
            if existing:
                messages.info(request, "Bu buyurtma allaqachon saqlangan.")
                return redirect("orders:detail", pk=existing.pk)
            form.add_error(None, "Saqlab bo'lmadi: bu telefon raqamli mijoz hozirgina qo'shilgan. Qaytadan urinib ko'ring.")
        else:
            messages.success(request, f"Buyurtma #{order.pk} yaratildi.")
            return redirect("orders:detail", pk=order.pk)

    found = _found_customer(form, initial_phone)
    phone_value = form["phone"].value() if "phone" in form.fields else ""
    return render(
        request,
        "orders/order_form.html",
        {
            "form": form,
            "is_new": True,
            "found_customer": found,
            "show_new_customer": found is None and bool(phone_value),
        },
    )


@boss_required
def order_edit(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer"), pk=pk)
    if not order.is_open:
        messages.warning(request, "Yakunlangan buyurtmani tahrirlab bo'lmaydi.")
        return redirect("orders:detail", pk=order.pk)

    form = OrderForm(request.POST or None, order=order)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            update_order(
                order,
                items=form.items,
                driver=data["driver"],
                delivery_date=data["delivery_date"],
                note=data["note"],
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("orders:detail", pk=order.pk)
        messages.success(request, "Buyurtma saqlandi.")
        return redirect("orders:detail", pk=order.pk)
    return render(
        request,
        "orders/order_form.html",
        {"form": form, "order": order, "is_new": False, "found_customer": order.customer},
    )


@boss_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer", "driver", "created_by", "recurring"), pk=pk)
    return render(
        request,
        "orders/order_detail.html",
        {"order": order, "items": order.items.select_related("product"), "drivers": active_drivers()},
    )


@boss_required
@require_POST
def order_assign(request, pk):
    order = get_object_or_404(Order, pk=pk)
    driver_id = request.POST.get("driver", "")
    driver = None
    if driver_id:
        driver = active_drivers().filter(pk=driver_id).first() if driver_id.isdigit() else None
        if driver is None:
            messages.error(request, "Yetkazuvchi topilmadi yoki bloklangan.")
            return redirect("orders:detail", pk=order.pk)
    if assign_driver(order, driver):
        messages.success(request, f"Biriktirildi: {driver}." if driver else "Yetkazuvchi olib tashlandi.")
    else:
        messages.error(request, "Yakunlangan buyurtmani o'zgartirib bo'lmaydi.")
    return redirect("orders:detail", pk=order.pk)


@boss_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if cancel_order(order):
        messages.success(request, f"Buyurtma #{order.pk} bekor qilindi.")
    else:
        messages.error(request, "Bu buyurtma allaqachon yakunlangan, bekor qilib bo'lmaydi.")
    return redirect("orders:detail", pk=order.pk)
