"""Mijozlar, qarzdorlar, butil (tara) hisobi va qarz to'lovlari."""

import re
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import boss_required
from core.phone import PHONE_RE, normalize_phone
from core.templatetags.formatting import format_som
from orders.models import Order

from .forms import BottleReturnForm, CustomerCreateForm, CustomerForm, PaymentForm, PickupTaskForm
from .models import BottlePickup, Customer
from .services import DuplicateSubmission, accept_payment, cancel_pickup, create_pickup, receive_bottles


def customer_search_q(text: str) -> Q:
    """Ism, manzil, mo'ljal yoki telefon raqamining bir qismi bo'yicha qidiruv."""
    q = Q(name__icontains=text) | Q(address__icontains=text) | Q(landmark__icontains=text)
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 3:
        q |= Q(phone__contains=digits) | Q(phone2__contains=digits)
    return q


def safe_next(request, default: str) -> str:
    """?next=... manzilini faqat o'z saytimizga tegishli bo'lsa ishlatamiz."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return default


@boss_required
def customer_list(request):
    text = request.GET.get("q", "").strip()
    ctype = request.GET.get("type", "")
    customers = Customer.objects.all()
    if text:
        customers = customers.filter(customer_search_q(text))
    if ctype in Customer.Type.values:
        customers = customers.filter(customer_type=ctype)
    page = Paginator(customers.order_by("name"), 30).get_page(request.GET.get("page"))
    return render(
        request,
        "customers/customer_list.html",
        {"page_obj": page, "q": text, "ctype": ctype, "types": Customer.Type.choices},
    )


@boss_required
def customer_create(request):
    initial = {"phone": request.GET.get("phone", "")}
    form = CustomerCreateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        messages.success(request, f"Mijoz qo'shildi: {customer.name}")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/customer_form.html", {"form": form, "is_new": True})


@boss_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "O'zgarishlar saqlandi.")
        return redirect("customers:detail", pk=customer.pk)
    return render(request, "customers/customer_form.html", {"form": form, "customer": customer, "is_new": False})


@boss_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.select_related("driver", "customer")
    summary = orders.aggregate(
        total=Count("id", filter=~Q(status=Order.Status.CANCELLED)),
        delivered=Count("id", filter=Q(status=Order.Status.DELIVERED)),
        paid=Coalesce(Sum("paid_amount", filter=Q(status=Order.Status.DELIVERED)), 0),
        last_delivery=Max("delivered_at", filter=Q(status=Order.Status.DELIVERED)),
    )
    pickups = customer.bottle_pickups.select_related("driver")
    return render(
        request,
        "customers/customer_detail.html",
        {
            "customer": customer,
            "orders": orders[:30],
            "payments": customer.payments.select_related("received_by")[:30],
            "recurring_orders": customer.recurring_orders.prefetch_related("items__product"),
            "pickups": pickups[:20],
            "open_pickup": next((p for p in pickups[:20] if p.is_open), None),
            "summary": summary,
        },
    )


@boss_required
def customer_payment(request, pk):
    """Qarz to'lovini qabul qilish."""
    customer = get_object_or_404(Customer, pk=pk)
    next_url = safe_next(request, reverse("customers:detail", args=[customer.pk]))

    if customer.debt <= 0 and request.method == "GET":
        messages.info(request, f"{customer.name}ning qarzi yo'q.")
        return redirect(next_url)

    form = PaymentForm(request.POST or None, customer=customer)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            accept_payment(
                customer=customer,
                amount=data["amount"],
                method=data["method"],
                date=data["date"],
                note=data["note"],
                user=request.user,
                client_token=data["token"],
            )
        except DuplicateSubmission:
            messages.info(request, "Bu to'lov allaqachon saqlangan.")
            return redirect(next_url)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{customer.name}: {format_som(data['amount'])} to'lov qabul qilindi.")
            return redirect(next_url)
    return render(
        request, "customers/payment_form.html", {"form": form, "customer": customer, "next_url": next_url}
    )


@boss_required
def debtors(request):
    """Qarzi bor mijozlar, eng katta qarzdan boshlab."""
    text = request.GET.get("q", "").strip()
    customers = Customer.objects.filter(debt__gt=0)
    totals = customers.aggregate(total=Coalesce(Sum("debt"), 0), count=Count("id"))
    if text:
        customers = customers.filter(customer_search_q(text))
    customers = customers.annotate(last_payment=Max("payments__date")).order_by("-debt", "name")
    page = Paginator(customers, 50).get_page(request.GET.get("page"))
    return render(request, "customers/debtors.html", {"page_obj": page, "totals": totals, "q": text})


# "Uzoq vaqt buyurtma bermagan" filtri: butillari qolib ketish xavfi bor mijozlar.
# 19 litrli suv odatda haftada bir olinadi, shuning uchun 2 hafta jimlik — belgi.
STALE_DAYS = 14
IDLE_FILTERS = [("", "Hammasi"), ("14", "2 haftadan beri buyurtmasiz"), ("30", "1 oydan beri buyurtmasiz")]


def delivered_since(days: int):
    """Mijozga oxirgi `days` kun ichida yetkazish bo'lganmi (subquery)."""
    since = timezone.now() - timedelta(days=days)
    return Exists(
        Order.objects.filter(customer=OuterRef("pk"), status=Order.Status.DELIVERED, delivered_at__gte=since)
    )


@boss_required
def bottles(request):
    """Butil (tara) hisobi: qaysi mijozda nechta zavod butili turibdi va qaysilari qolib ketgan."""
    text = request.GET.get("q", "").strip()
    idle = request.GET.get("idle", "")
    if idle not in dict(IDLE_FILTERS):
        idle = ""

    delivered = Order.objects.filter(status=Order.Status.DELIVERED)
    picked = BottlePickup.objects.filter(status=BottlePickup.Status.DONE).aggregate(s=Coalesce(Sum("quantity"), 0))["s"]
    with_bottles = Customer.objects.filter(bottles__gt=0)
    stale = with_bottles.filter(~delivered_since(STALE_DAYS)).aggregate(count=Count("id"), bottles=Coalesce(Sum("bottles"), 0))
    totals = {
        "at_customers": Customer.objects.aggregate(s=Coalesce(Sum("bottles"), 0))["s"],
        "given": delivered.aggregate(s=Coalesce(Sum("bottles_given"), 0))["s"],
        "returned": delivered.aggregate(s=Coalesce(Sum("returned_bottles"), 0))["s"] + picked,
        "picked": picked,
        "customers": with_bottles.count(),
        "stale": stale,
    }
    open_pickups = (
        BottlePickup.objects.filter(status=BottlePickup.Status.PLANNED)
        .select_related("customer", "driver")
        .order_by("date", "created_at")
    )

    customers = with_bottles
    if text:
        customers = customers.filter(customer_search_q(text))
    if idle:
        customers = customers.filter(~delivered_since(int(idle)))
    customers = customers.annotate(
        last_delivery=Max("orders__delivered_at", filter=Q(orders__status=Order.Status.DELIVERED))
    ).prefetch_related(
        Prefetch(
            "bottle_pickups",
            queryset=BottlePickup.objects.filter(status=BottlePickup.Status.PLANNED).select_related("driver"),
            to_attr="open_pickups",
        )
    )
    page = Paginator(customers.order_by("-bottles", "name"), 50).get_page(request.GET.get("page"))
    return render(
        request,
        "customers/bottles.html",
        {
            "page_obj": page,
            "totals": totals,
            "q": text,
            "idle": idle,
            "idle_filters": IDLE_FILTERS,
            "open_pickups": open_pickups,
            "today": timezone.localdate(),
        },
    )


@boss_required
def bottle_return(request, pk):
    """Mijoz butillarni o'zi olib keldi — darhol qabul qilish."""
    customer = get_object_or_404(Customer, pk=pk)
    next_url = safe_next(request, reverse("customers:detail", args=[customer.pk]))
    if not customer.bottles and request.method == "GET":
        messages.info(request, f"{customer.name}: mijozda butil yo'q.")
        return redirect(next_url)

    form = BottleReturnForm(request.POST or None, customer=customer)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            receive_bottles(
                customer=customer,
                quantity=data["quantity"],
                date=data["date"],
                note=data["note"],
                user=request.user,
                client_token=data["token"],
            )
        except DuplicateSubmission:
            messages.info(request, "Bu yozuv allaqachon saqlangan.")
            return redirect(next_url)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{customer.name}: {data['quantity']} ta butil qabul qilindi.")
            return redirect(next_url)
    return render(
        request,
        "customers/bottle_form.html",
        {"form": form, "customer": customer, "next_url": next_url, "mode": "return"},
    )


@boss_required
def pickup_create(request, pk):
    """Yetkazuvchiga "shu mijozdan butillarni olib kel" topshirig'ini berish."""
    customer = get_object_or_404(Customer, pk=pk)
    next_url = safe_next(request, reverse("customers:detail", args=[customer.pk]))
    if request.method == "GET":
        if not customer.bottles:
            messages.info(request, f"{customer.name}: mijozda butil yo'q.")
            return redirect(next_url)
        open_pickup = customer.bottle_pickups.filter(status=BottlePickup.Status.PLANNED).select_related("driver").first()
        if open_pickup:
            messages.info(
                request,
                f"{customer.name}: ochiq topshiriq allaqachon bor ({open_pickup.driver}, {open_pickup.date:%d.%m.%Y}).",
            )
            return redirect(next_url)

    form = PickupTaskForm(request.POST or None, customer=customer)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_pickup(
                customer=customer,
                driver=data["driver"],
                date=data["date"],
                note=data["note"],
                user=request.user,
                client_token=data["token"],
            )
        except DuplicateSubmission:
            messages.info(request, "Bu topshiriq allaqachon saqlangan.")
            return redirect(next_url)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                f"Topshiriq berildi: {data['driver']} {data['date']:%d.%m.%Y} kuni "
                f"{customer.name}dan butillarni olib keladi.",
            )
            return redirect(next_url)
    return render(
        request,
        "customers/bottle_form.html",
        {"form": form, "customer": customer, "next_url": next_url, "mode": "pickup"},
    )


@boss_required
@require_POST
def pickup_cancel(request, pk):
    """Butil olib kelish topshirig'ini bekor qilish."""
    pickup = get_object_or_404(BottlePickup.objects.select_related("customer"), pk=pk)
    next_url = safe_next(request, reverse("customers:detail", args=[pickup.customer_id]))
    if cancel_pickup(pickup):
        messages.success(request, f"{pickup.customer.name}: topshiriq bekor qilindi.")
    else:
        messages.info(request, "Topshiriq allaqachon yakunlangan.")
    return redirect(next_url)


@boss_required
def customer_lookup(request):
    """Telefon bo'yicha mijozni topish (yangi buyurtma formasi uchun, JSON)."""
    phone = normalize_phone(request.GET.get("phone", ""))
    if not PHONE_RE.match(phone):
        return JsonResponse({"found": False, "valid": False})
    customer = Customer.objects.filter(phone=phone).first()
    if not customer:
        return JsonResponse({"found": False, "valid": True})
    return JsonResponse(
        {
            "found": True,
            "valid": True,
            "id": customer.pk,
            "name": customer.name,
            "address": customer.address,
            "landmark": customer.landmark,
            "debt": customer.debt,
            "debt_display": format_som(customer.debt),
            "bottles": customer.bottles,
            "url": reverse("customers:detail", args=[customer.pk]),
        }
    )
