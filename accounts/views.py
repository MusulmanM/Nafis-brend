"""Login, rolga qarab yo'naltirish va yetkazuvchilarni boshqarish."""

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order
from reports.stats import driver_stats

from .decorators import boss_required
from .forms import DriverCreateForm, DriverUpdateForm, LoginForm
from .models import User


class LoginView(auth_views.LoginView):
    """Yagona login sahifasi (boshliq ham, yetkazuvchi ham shu yerdan kiradi)."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True  # kirgan foydalanuvchi login sahifasini ko'rmaydi


@login_required
def home(request):
    """Kirgandan keyin rolga qarab tegishli panelga yo'naltiradi."""
    if request.user.is_boss:
        return redirect("reports:dashboard")
    return redirect("driver:today")


# --- Yetkazuvchilar (faqat boshliq uchun) ------------------------------------


def get_driver(pk):
    return get_object_or_404(User, pk=pk, role=User.Role.DRIVER)


@boss_required
def driver_list(request):
    today = timezone.localdate()
    today_q = Q(orders__delivery_date=today)
    drivers = (
        User.objects.filter(role=User.Role.DRIVER)
        .annotate(
            today_total=Count("orders", filter=today_q & ~Q(orders__status=Order.Status.CANCELLED)),
            today_delivered=Count("orders", filter=today_q & Q(orders__status=Order.Status.DELIVERED)),
            today_pending=Count("orders", filter=today_q & Q(orders__status__in=Order.OPEN_STATUSES)),
        )
        .order_by("-is_active", "first_name", "username")
    )
    return render(request, "accounts/driver_list.html", {"drivers": drivers})


@boss_required
def driver_create(request):
    form = DriverCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        driver = form.save()
        messages.success(request, f"Yetkazuvchi qo'shildi: {driver}. Login: {driver.username}")
        return redirect("accounts:driver_detail", pk=driver.pk)
    return render(request, "accounts/driver_form.html", {"form": form, "is_new": True})


@boss_required
def driver_edit(request, pk):
    driver = get_driver(pk)
    form = DriverUpdateForm(request.POST or None, instance=driver)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "O'zgarishlar saqlandi.")
        return redirect("accounts:driver_detail", pk=driver.pk)
    return render(request, "accounts/driver_form.html", {"form": form, "driver": driver, "is_new": False})


@boss_required
@require_POST
def driver_toggle_active(request, pk):
    """Yetkazuvchini bloklash yoki blokdan chiqarish."""
    driver = get_driver(pk)
    driver.is_active = not driver.is_active
    driver.save(update_fields=["is_active"])
    if driver.is_active:
        messages.success(request, f"{driver} blokdan chiqarildi.")
    else:
        open_orders = driver.orders.filter(status__in=Order.OPEN_STATUSES).count()
        open_pickups = driver.bottle_pickups.filter(status="planned").count()
        text = f"{driver} bloklandi — endi tizimga kira olmaydi."
        if open_orders:
            text += f" Unda {open_orders} ta yakunlanmagan buyurtma bor, ularni boshqa yetkazuvchiga biriktiring."
        if open_pickups:
            text += f" {open_pickups} ta butil olib kelish topshirig'i ochiq — ularni bekor qilib, qayta bering."
        messages.warning(request, text)
    return redirect("accounts:driver_detail", pk=driver.pk)


@boss_required
def driver_detail(request, pk):
    driver = get_driver(pk)
    today = timezone.localdate()
    periods = [
        ("Bugun", today, today),
        ("Shu oy", today.replace(day=1), today),
        ("Hammasi", None, None),
    ]
    stats = [{"label": label, **driver_stats(driver, start, end)} for label, start, end in periods]
    open_orders = (
        driver.orders.filter(status__in=Order.OPEN_STATUSES).select_related("customer").order_by("delivery_date")
    )
    recent_orders = driver.orders.exclude(status__in=Order.OPEN_STATUSES).select_related("customer")[:15]
    return render(
        request,
        "accounts/driver_detail.html",
        {"driver": driver, "stats": stats, "open_orders": open_orders, "recent_orders": recent_orders},
    )
