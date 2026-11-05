"""
Yetkazuvchi paneli (telefon uchun).

Yetkazuvchi faqat O'ZIGA biriktirilgan buyurtmalar va butil olib kelish
topshiriqlarini ko'radi va o'zgartiradi: har bir so'rovda `driver=request.user`
sharti bilan olinadi, boshqa yetkazuvchiniki uchun 404 qaytadi.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Case, Count, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import driver_required
from core.choices import PaymentType
from core.templatetags.formatting import format_som
from customers.models import BottlePickup
from customers.services import PickupClosed, complete_pickup, fail_pickup

from .forms import DeliveryForm, FailForm, PickupDoneForm
from .models import Order
from .services import OrderClosed, mark_delivered, mark_failed, start_delivery


def my_orders(request):
    return Order.objects.filter(driver=request.user).select_related("customer")


def get_my_order(request, pk):
    return get_object_or_404(my_orders(request), pk=pk)


def form_prefix(order) -> str:
    # Bir sahifada ko'p buyurtma formasi bo'lgani uchun har biriga alohida prefiks
    return f"o{order.pk}"


def my_pickups(request):
    return BottlePickup.objects.filter(driver=request.user).select_related("customer")


def get_my_pickup(request, pk):
    return get_object_or_404(my_pickups(request), pk=pk)


def pickup_prefix(pickup) -> str:
    return f"p{pickup.pk}"


@driver_required
def today(request):
    """Bugungi (va kechikkan) buyurtmalarim — kartochkalar ko'rinishida."""
    day = timezone.localdate()
    open_orders = (
        my_orders(request)
        .filter(status__in=Order.OPEN_STATUSES, delivery_date__lte=day)
        .prefetch_related("items__product")
        # Avval "yo'lda", keyin "yangi"; ichida — eng eskisi birinchi
        .annotate(
            sort=Case(When(status=Order.Status.ON_THE_WAY, then=Value(0)), default=Value(1), output_field=IntegerField())
        )
        .order_by("sort", "delivery_date", "created_at")
    )
    for order in open_orders:
        order.deliver_form = DeliveryForm(order=order, prefix=form_prefix(order))
        order.fail_form = FailForm(prefix=form_prefix(order))

    # Butil olib kelish topshiriqlari (bugungi va kechikkanlar)
    pickups = list(
        my_pickups(request).filter(status=BottlePickup.Status.PLANNED, date__lte=day).order_by("date", "created_at")
    )
    for pickup in pickups:
        pickup.done_form = PickupDoneForm(pickup=pickup, prefix=pickup_prefix(pickup))
        pickup.fail_form = FailForm(prefix=pickup_prefix(pickup))

    done = (
        my_orders(request)
        .filter(
            Q(status=Order.Status.DELIVERED, delivered_at__date=day)
            | Q(status=Order.Status.FAILED, delivery_date=day)
        )
        .order_by("-updated_at")
    )
    done_pickups = my_pickups(request).filter(
        status__in=[BottlePickup.Status.DONE, BottlePickup.Status.FAILED], date=day
    )
    return render(
        request,
        "driver/today.html",
        {
            "open_orders": open_orders,
            "pickups": pickups,
            "done": done,
            "done_pickups": done_pickups,
            "today": day,
        },
    )


@driver_required
@require_POST
def start(request, pk):
    order = get_my_order(request, pk)
    if start_delivery(order, request.user):
        messages.success(request, f"#{order.pk} — yo'ldasiz. Omad!")
    else:
        messages.info(request, "Buyurtma holati allaqachon o'zgargan.")
    return redirect("driver:today")


@driver_required
def deliver(request, pk):
    """"Yetkazib berdim". Odatda oynadan (modal) yuboriladi; xato bo'lsa — alohida sahifa."""
    order = get_my_order(request, pk)
    if not order.is_open:
        messages.info(request, f"#{order.pk} allaqachon yakunlangan.")
        return redirect("driver:today")

    form = DeliveryForm(request.POST or None, order=order, prefix=form_prefix(order))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            mark_delivered(
                order,
                driver=request.user,
                payment_type=data["payment_type"],
                paid_amount=data["paid_amount"],
                returned_bottles=data["returned_bottles"],
            )
        except OrderClosed:
            messages.info(request, f"#{order.pk} allaqachon yakunlangan.")
            return redirect("driver:today")
        except ValidationError as error:
            form.add_error(None, error)
        else:
            text = f"#{order.pk} yetkazildi."
            if data["paid_amount"]:
                text += f" Olindi: {format_som(data['paid_amount'])}."
            messages.success(request, text)
            return redirect("driver:today")
    return render(request, "driver/deliver.html", {"order": order, "form": form})


@driver_required
def fail(request, pk):
    """"Yetkazib bo'lmadi" — sabab bilan."""
    order = get_my_order(request, pk)
    if not order.is_open:
        messages.info(request, f"#{order.pk} allaqachon yakunlangan.")
        return redirect("driver:today")

    form = FailForm(request.POST or None, prefix=form_prefix(order))
    if request.method == "POST" and form.is_valid():
        if mark_failed(order, driver=request.user, reason=form.cleaned_data["reason"], note=form.cleaned_data["note"]):
            messages.warning(request, f"#{order.pk} — yetkazib bo'lmadi deb belgilandi.")
        else:
            messages.info(request, f"#{order.pk} allaqachon yakunlangan.")
        return redirect("driver:today")
    return render(request, "driver/fail.html", {"order": order, "form": form})


@driver_required
def pickup_done(request, pk):
    """"Olib keldim" — mijozdan bo'sh butillar olib kelindi."""
    pickup = get_my_pickup(request, pk)
    if not pickup.is_open:
        messages.info(request, f"{pickup.customer.name}: topshiriq allaqachon yakunlangan.")
        return redirect("driver:today")

    form = PickupDoneForm(request.POST or None, pickup=pickup, prefix=pickup_prefix(pickup))
    if request.method == "POST" and form.is_valid():
        quantity = form.cleaned_data["quantity"]
        try:
            complete_pickup(pickup, driver=request.user, quantity=quantity)
        except PickupClosed:
            messages.info(request, f"{pickup.customer.name}: topshiriq allaqachon yakunlangan.")
            return redirect("driver:today")
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"{pickup.customer.name}: {quantity} ta butil olib kelindi.")
            return redirect("driver:today")
    return render(request, "driver/pickup_done.html", {"pickup": pickup, "form": form})


@driver_required
def pickup_fail(request, pk):
    """Butillarni olib kelib bo'lmadi — sabab bilan."""
    pickup = get_my_pickup(request, pk)
    if not pickup.is_open:
        messages.info(request, f"{pickup.customer.name}: topshiriq allaqachon yakunlangan.")
        return redirect("driver:today")

    form = FailForm(request.POST or None, prefix=pickup_prefix(pickup))
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if fail_pickup(pickup, driver=request.user, reason=data["reason"], note=data["note"]):
            messages.warning(request, f"{pickup.customer.name}: butillarni olib kelib bo'lmadi deb belgilandi.")
        else:
            messages.info(request, f"{pickup.customer.name}: topshiriq allaqachon yakunlangan.")
        return redirect("driver:today")
    return render(request, "driver/pickup_fail.html", {"pickup": pickup, "form": form})


@driver_required
def my_day(request):
    """Mening kunim: nechta yetkazdim, nechtasi qoldi, qancha pul yig'dim."""
    day = timezone.localdate()
    mine = my_orders(request)
    delivered = mine.filter(status=Order.Status.DELIVERED, delivered_at__date=day)

    def paid_by(kind):
        return Coalesce(Sum("paid_amount", filter=Q(payment_type=kind)), 0)

    money = delivered.aggregate(
        count=Count("id"),
        total=Coalesce(Sum("paid_amount"), 0),
        cash=paid_by(PaymentType.CASH),
        card=paid_by(PaymentType.CARD),
        click=paid_by(PaymentType.CLICK),
        payme=paid_by(PaymentType.PAYME),
        debt=Coalesce(Sum(F("total_amount") - F("paid_amount"), filter=Q(total_amount__gt=F("paid_amount"))), 0),
        bottles_given=Coalesce(Sum("bottles_given"), 0),
        bottles_returned=Coalesce(Sum("returned_bottles"), 0),
    )
    by_type = [
        ("Naqd", money["cash"]),
        ("Karta", money["card"]),
        ("Click", money["click"]),
        ("Payme", money["payme"]),
        ("Qarzga berildi", money["debt"]),
    ]
    pickups = my_pickups(request).filter(date=day).aggregate(
        done=Count("id", filter=Q(status=BottlePickup.Status.DONE)),
        bottles=Coalesce(Sum("quantity", filter=Q(status=BottlePickup.Status.DONE)), 0),
    )
    pickups["remaining"] = my_pickups(request).filter(status=BottlePickup.Status.PLANNED, date__lte=day).count()
    context = {
        "today": day,
        "money": money,
        "by_type": by_type,
        "pickups": pickups,
        "remaining": mine.filter(status__in=Order.OPEN_STATUSES, delivery_date__lte=day).count(),
        "failed": mine.filter(status=Order.Status.FAILED, delivery_date=day).count(),
        "delivered_orders": delivered.order_by("-delivered_at"),
    }
    return render(request, "driver/my_day.html", context)
