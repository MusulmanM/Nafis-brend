"""
Buyurtmalar bilan ishlaydigan amallar.

Muhim qoida: holatni o'zgartirish "shartli UPDATE" bilan bajariladi —
masalan, "agar buyurtma hali ochiq bo'lsa, bekor qil". Bu bitta SQL so'rov,
shuning uchun bir vaqtda ikki kishi (boshliq va yetkazuvchi) bir buyurtmani
o'zgartirsa ham, faqat bittasi muvaffaqiyatli bo'ladi.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from core.choices import PaymentType
from core.templatetags.formatting import format_som
from customers.models import Customer

from .models import Order, OrderItem

NOT_EDITABLE = "Buyurtma allaqachon yakunlangan, uni o'zgartirib bo'lmaydi."


class OrderClosed(Exception):
    """Buyurtma allaqachon yakunlangan (masalan, tugma ikkinchi marta bosilgan)."""


@transaction.atomic
def create_order(
    *, customer, items, delivery_date, driver=None, note="", user=None, client_token=None, recurring=None
) -> Order:
    """Yangi buyurtma. `items` — {mahsulot: soni} lug'ati.

    Narx mahsulotning HOZIRGI narxidan olinib, buyurtma qatorida saqlanadi.
    """
    order = Order.objects.create(
        customer=customer,
        driver=driver,
        delivery_date=delivery_date,
        note=note,
        created_by=user,
        client_token=client_token,
        recurring=recurring,
    )
    OrderItem.objects.bulk_create(
        [OrderItem(order=order, product=product, quantity=qty, price=product.price) for product, qty in items.items()]
    )
    order.update_total()
    return order


def _open_orders(order):
    """Faqat hali yakunlanmagan (yangi yoki yo'lda) shu buyurtma."""
    return Order.objects.filter(pk=order.pk, status__in=Order.OPEN_STATUSES)


@transaction.atomic
def update_order(order, *, items, driver, delivery_date, note) -> Order:
    """Yakunlanmagan buyurtmani tahrirlash."""
    changes = {"driver": driver, "delivery_date": delivery_date, "note": note, "updated_at": timezone.now()}
    if (driver.pk if driver else None) != order.driver_id:
        # Yetkazuvchi almashsa, yangi yetkazuvchi uchun buyurtma yana "yangi" bo'ladi
        changes["status"] = Order.Status.NEW
    if not _open_orders(order).update(**changes):
        raise ValidationError(NOT_EDITABLE)

    current = {item.product_id: item for item in order.items.all()}
    for product, qty in items.items():
        item = current.pop(product.pk, None)
        if item is None:
            OrderItem.objects.create(order=order, product=product, quantity=qty, price=product.price)
        elif item.quantity != qty:
            item.quantity = qty
            item.save(update_fields=["quantity"])
    # Formada soni 0 qilingan mahsulotlar buyurtmadan olib tashlanadi
    for item in current.values():
        item.delete()

    order.refresh_from_db()
    order.update_total()
    return order


def assign_driver(order, driver) -> bool:
    """Buyurtmani yetkazuvchiga biriktirish. Yakunlangan bo'lsa, False qaytaradi."""
    changes = {"driver": driver, "updated_at": timezone.now()}
    if (driver.pk if driver else None) != order.driver_id:
        changes["status"] = Order.Status.NEW
    return bool(_open_orders(order).update(**changes))


def cancel_order(order) -> bool:
    """Buyurtmani bekor qilish. Yakunlangan bo'lsa, False qaytaradi."""
    return bool(_open_orders(order).update(status=Order.Status.CANCELLED, updated_at=timezone.now()))


# --- Yetkazuvchi amallari ------------------------------------------------------


def start_delivery(order, driver) -> bool:
    """"Yo'lga chiqdim": yangi -> yo'lda. Faqat o'ziga biriktirilgan buyurtma uchun."""
    return bool(
        Order.objects.filter(pk=order.pk, driver=driver, status=Order.Status.NEW).update(
            status=Order.Status.ON_THE_WAY, updated_at=timezone.now()
        )
    )


def mark_delivered(order, *, driver, payment_type, paid_amount, returned_bottles, at=None) -> Order:
    """"Yetkazib berdim": buyurtmani yakunlaydi va mijoz balansini yangilaydi.

    Mijoz qarzi:     qarz += buyurtma summasi − olingan summa
                     (manfiy bo'lsa — mijoz eski qarzini ham to'lagan)
    Mijoz butillari: butillar += berilgan to'la butillar − qaytarilgan bo'shlar

    Ikki marta hisoblanmasligi uchun holat shartli UPDATE bilan o'zgartiriladi:
    "faqat hali yakunlanmagan bo'lsa". Ikkinchi bosishda 0 qator yangilanadi va
    OrderClosed xatosi chiqadi — qarz va butillarga tegilmaydi.
    """
    if payment_type == PaymentType.DEBT:
        paid_amount = 0
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status not in Order.OPEN_STATUSES:
                raise OrderClosed
            if driver is not None and order.driver_id != driver.pk:
                raise OrderClosed
            customer = Customer.objects.select_for_update().get(pk=order.customer_id)
            given = order.calculate_returnable_bottles()

            if paid_amount < 0 or returned_bottles < 0:
                raise ValidationError("Manfiy qiymat kiritib bo'lmaydi.")
            if paid_amount > order.total_amount + customer.debt:
                raise ValidationError(
                    f"Olingan summa buyurtma va eski qarz yig'indisidan "
                    f"({format_som(order.total_amount + customer.debt)}) katta bo'lmasin."
                )
            if returned_bottles > customer.bottles + given:
                raise ValidationError(f"Mijozda ko'pi bilan {customer.bottles + given} ta butil bor.")

            updated = Order.objects.filter(pk=order.pk, status__in=Order.OPEN_STATUSES).update(
                status=Order.Status.DELIVERED,
                payment_type=payment_type,
                paid_amount=paid_amount,
                bottles_given=given,
                returned_bottles=returned_bottles,
                delivered_at=at or timezone.now(),
                fail_reason="",
                fail_note="",
                updated_at=timezone.now(),
            )
            if not updated:
                raise OrderClosed
            Customer.objects.filter(pk=customer.pk).update(
                debt=F("debt") + (order.total_amount - paid_amount),
                bottles=F("bottles") + (given - returned_bottles),
            )
    except IntegrityError:
        # Bazadagi cheklov (qarz/butil manfiy bo'lolmaydi) — balans shu paytda o'zgargan
        raise ValidationError("Mijoz balansi hozirgina o'zgardi. Qaytadan urinib ko'ring.") from None
    order.refresh_from_db()
    return order


def mark_failed(order, *, driver, reason, note="") -> bool:
    """"Yetkazib bo'lmadi". Balans o'zgarmaydi. Yakunlangan bo'lsa, False qaytaradi."""
    orders = Order.objects.filter(pk=order.pk, status__in=Order.OPEN_STATUSES)
    if driver is not None:
        orders = orders.filter(driver=driver)
    return bool(
        orders.update(status=Order.Status.FAILED, fail_reason=reason, fail_note=note, updated_at=timezone.now())
    )
