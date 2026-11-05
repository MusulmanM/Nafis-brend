"""Ombor (ishlab chiqarish, qoldiq) va mahsulotlar."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import boss_required

from .forms import ProductForm, StockEntryForm
from .models import Product, StockEntry
from .stock import stock_summary


@boss_required
def stock(request):
    """Ombor: ishlab chiqarishni kiritish va qoldiqni ko'rish."""
    today = timezone.localdate()
    form = StockEntryForm(request.POST or None, initial={"date": today})
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.created_by = request.user
        entry.save()
        messages.success(request, f"Kiritildi: {entry.product} — {entry.quantity} ta.")
        return redirect("inventory:stock")
    entries = StockEntry.objects.select_related("product", "created_by")[:30]
    return render(
        request,
        "inventory/stock.html",
        {"form": form, "rows": stock_summary(today), "entries": entries, "today": today},
    )


@boss_required
@require_POST
def stock_entry_delete(request, pk):
    entry = get_object_or_404(StockEntry, pk=pk)
    entry.delete()
    messages.success(request, "Yozuv o'chirildi.")
    return redirect("inventory:stock")


@boss_required
def product_list(request):
    return render(request, "inventory/product_list.html", {"products": Product.objects.all()})


@boss_required
def product_create(request):
    form = ProductForm(request.POST or None, initial={"is_active": True})
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Mahsulot qo'shildi: {product}")
        return redirect("inventory:product_list")
    return render(request, "inventory/product_form.html", {"form": form, "is_new": True})


@boss_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "O'zgarishlar saqlandi. Yangi narx faqat yangi buyurtmalarga qo'llanadi.")
        return redirect("inventory:product_list")
    return render(request, "inventory/product_form.html", {"form": form, "product": product, "is_new": False})
