"""
Mijoz balansini o'zgartiradigan amallar.

Qarz (to'lovlar) va buyurtmasiz butil qaytarish faqat shu yerdagi funksiyalar
orqali o'zgaradi. Hammasi
`transaction.atomic()` ichida: yo hammasi saqlanadi, yo hech narsa.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import BottlePickup, Customer, Payment


class DuplicateSubmission(Exception):
    """Shu forma allaqachon yuborilgan (tugma ikki marta bosilgan)."""


class PickupClosed(Exception):
    """Butil olib kelish topshirig'i allaqachon yakunlangan yoki bekor qilingan."""


def accept_payment(*, customer, amount, method, date, note, user, client_token) -> Payment:
    """Qarz to'lovini qabul qiladi va mijoz qarzini kamaytiradi.

    Ikki marta hisoblanmasligi uchun ikki himoya bor:
      1) `client_token` takrorlanmas (unique) — bir xil forma ikkinchi marta
         yuborilsa, baza yozuvni qabul qilmaydi va hammasi bekor bo'ladi;
      2) qarz shartli UPDATE bilan kamaytiriladi: "qarz >= summa bo'lsa"
         — shuning uchun qarz hech qachon manfiy bo'lmaydi.
    """
    if amount <= 0:
        raise ValidationError("Summa musbat bo'lishi kerak.")
    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                customer=customer,
                amount=amount,
                method=method,
                date=date,
                note=note,
                received_by=user,
                client_token=client_token,
            )
            updated = Customer.objects.filter(pk=customer.pk, debt__gte=amount).update(debt=F("debt") - amount)
            if not updated:
                # atomic() bloki ichida xato — yuqoridagi to'lov yozuvi ham bekor qilinadi
                raise ValidationError("To'lov summasi mijozning hozirgi qarzidan katta.")
    except IntegrityError:
        if Payment.objects.filter(client_token=client_token).exists():
            raise DuplicateSubmission from None
        raise
    return payment


# --- Butillarni buyurtmasiz qaytarib olish -------------------------------------


def _take_bottles(customer_id, quantity):
    """Mijozdagi butillarni kamaytiradi (shartli UPDATE: "mijozda shuncha bor bo'lsa").

    Yetarli bo'lmasa, ValidationError — u atomic() blokidagi hamma narsani bekor qiladi.
    """
    if quantity <= 0:
        raise ValidationError("Butillar soni musbat bo'lishi kerak.")
    updated = Customer.objects.filter(pk=customer_id, bottles__gte=quantity).update(bottles=F("bottles") - quantity)
    if not updated:
        left = Customer.objects.filter(pk=customer_id).values_list("bottles", flat=True).first() or 0
        raise ValidationError(f"Mijozda hozir {left} ta butil bor — undan ko'p qaytarib bo'lmaydi.")


def receive_bottles(*, customer, quantity, date, note, user, client_token) -> BottlePickup:
    """Mijoz butillarni o'zi olib keldi — darhol "olib kelindi" deb yoziladi."""
    try:
        with transaction.atomic():
            pickup = BottlePickup.objects.create(
                customer=customer,
                status=BottlePickup.Status.DONE,
                quantity=quantity,
                date=date,
                note=note,
                created_by=user,
                done_at=timezone.now(),
                client_token=client_token,
            )
            _take_bottles(customer.pk, quantity)
    except IntegrityError:
        if BottlePickup.objects.filter(client_token=client_token).exists():
            raise DuplicateSubmission from None
        raise
    return pickup


def create_pickup(*, customer, driver, date, note="", user=None, client_token=None) -> BottlePickup:
    """Yetkazuvchiga "shu mijozdan butillarni olib kel" topshirig'i. Balans hali o'zgarmaydi."""
    try:
        with transaction.atomic():
            return BottlePickup.objects.create(
                customer=customer, driver=driver, date=date, note=note, created_by=user, client_token=client_token
            )
    except IntegrityError:
        if client_token and BottlePickup.objects.filter(client_token=client_token).exists():
            raise DuplicateSubmission from None
        # Bazadagi cheklov: bitta mijozga bitta ochiq topshiriq
        raise ValidationError("Bu mijoz uchun ochiq topshiriq allaqachon bor.") from None


def _open_pickup(pickup, driver=None):
    pickups = BottlePickup.objects.filter(pk=pickup.pk, status=BottlePickup.Status.PLANNED)
    if driver is not None:
        pickups = pickups.filter(driver=driver)
    return pickups


def complete_pickup(pickup, *, driver, quantity, at=None) -> BottlePickup:
    """"Olib keldim": topshiriq yakunlanadi va mijozdagi butillar kamayadi.

    Holat shartli UPDATE bilan o'zgaradi ("hali ochiq bo'lsa"), shuning uchun
    tugma ikki marta bosilsa ham butillar bir marta ayiriladi.
    """
    at = at or timezone.now()
    with transaction.atomic():
        changed = _open_pickup(pickup, driver).update(
            status=BottlePickup.Status.DONE,
            quantity=quantity,
            done_at=at,
            date=timezone.localdate(at),  # haqiqatda olib kelingan kun
            updated_at=timezone.now(),
        )
        if not changed:
            raise PickupClosed
        _take_bottles(pickup.customer_id, quantity)
    pickup.refresh_from_db()
    return pickup


def fail_pickup(pickup, *, driver, reason, note="") -> bool:
    """"Bo'lmadi". Balans o'zgarmaydi. Yakunlangan bo'lsa, False qaytaradi."""
    return bool(
        _open_pickup(pickup, driver).update(
            status=BottlePickup.Status.FAILED, fail_reason=reason, fail_note=note, updated_at=timezone.now()
        )
    )


def cancel_pickup(pickup) -> bool:
    """Boshliq topshiriqni bekor qiladi. Yakunlangan bo'lsa, False qaytaradi."""
    return bool(_open_pickup(pickup).update(status=BottlePickup.Status.CANCELLED, updated_at=timezone.now()))
