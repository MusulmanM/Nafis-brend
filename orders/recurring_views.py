"""Doimiy buyurtmalar (boshliq uchun): ro'yxat, qo'shish, tahrirlash, o'chirish."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import boss_required
from customers.models import Customer

from .forms import RecurringOrderForm
from .models import RecurringOrder, RecurringOrderItem
from .recurring import create_recurring_orders


@boss_required
def recurring_list(request):
    today = timezone.localdate()
    items = (
        RecurringOrder.objects.select_related("customer", "driver")
        .prefetch_related("items__product")
        .order_by("-is_active", "customer__name")
    )
    return render(request, "orders/recurring_list.html", {"recurring_orders": items, "today": today})


def _save(form, recurring=None):
    """Formadagi ma'lumotlarni doimiy buyurtma va uning mahsulotlariga yozadi."""
    data = form.cleaned_data
    with transaction.atomic():
        if recurring is None:
            recurring = RecurringOrder(customer=form.customer)
        recurring.weekdays = form.weekdays_value()
        recurring.driver = data["driver"]
        recurring.note = data["note"]
        recurring.is_active = data["is_active"]
        recurring.save()
        recurring.items.all().delete()
        RecurringOrderItem.objects.bulk_create(
            [RecurringOrderItem(recurring_order=recurring, product=p, quantity=q) for p, q in form.items.items()]
        )
    return recurring


@boss_required
def recurring_create(request):
    initial = {"is_active": True}
    customer_id = request.GET.get("customer", "")
    if customer_id.isdigit():
        customer = Customer.objects.filter(pk=customer_id).first()
        if customer:
            initial["phone"] = customer.phone
    form = RecurringOrderForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        recurring = _save(form)
        messages.success(request, f"Doimiy buyurtma qo'shildi: {recurring}")
        return redirect("orders:recurring_list")
    return render(request, "orders/recurring_form.html", {"form": form, "is_new": True})


@boss_required
def recurring_edit(request, pk):
    recurring = get_object_or_404(RecurringOrder.objects.select_related("customer"), pk=pk)
    form = RecurringOrderForm(request.POST or None, recurring=recurring)
    if request.method == "POST" and form.is_valid():
        _save(form, recurring)
        messages.success(request, "Saqlandi.")
        return redirect("orders:recurring_list")
    return render(request, "orders/recurring_form.html", {"form": form, "recurring": recurring, "is_new": False})


@boss_required
@require_POST
def recurring_delete(request, pk):
    recurring = get_object_or_404(RecurringOrder, pk=pk)
    recurring.delete()  # yaratilgan buyurtmalar o'chmaydi, faqat bog'lanish uziladi
    messages.success(request, "Doimiy buyurtma o'chirildi.")
    return redirect("orders:recurring_list")


@boss_required
@require_POST
def recurring_run(request):
    """Bugun uchun doimiy buyurtmalarni qo'lda yaratish (buyruqni kutmasdan)."""
    result = create_recurring_orders(timezone.localdate(), user=request.user)
    created = len(result["created"])
    if created:
        messages.success(request, f"Bugun uchun {created} ta buyurtma yaratildi.")
    else:
        messages.info(request, "Bugun uchun yangi buyurtma yaratilmadi (avvaldan bor yoki bugun ularning kuni emas).")
    return redirect("orders:recurring_list")
