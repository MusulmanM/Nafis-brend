"""Bir nechta app'da ishlatiladigan umumiy tanlovlar (choices)."""

from django.db import models


class PaymentType(models.TextChoices):
    """To'lov turlari. Buyurtmada "qarzga" ham bo'lishi mumkin."""

    CASH = "cash", "Naqd"
    CARD = "card", "Karta"
    CLICK = "click", "Click"
    PAYME = "payme", "Payme"
    DEBT = "debt", "Qarzga"


# Qarzni to'lashda "qarzga" turi ma'noga ega emas, shuning uchun uni chiqarib tashlaymiz
PAYMENT_METHOD_CHOICES = [c for c in PaymentType.choices if c[0] != PaymentType.DEBT]


class FailReason(models.TextChoices):
    """Yetkazuvchi manzilga borib, ishni bajara olmagan sabablar.

    Buyurtma ("yetkazib bo'lmadi") va butil olib kelish topshirig'ida bir xil.
    """

    NOT_HOME = "not_home", "Uyda yo'q"
    NO_ANSWER = "no_answer", "Telefon ko'tarmadi"
    WRONG_ADDRESS = "wrong_address", "Manzil noto'g'ri"
    OTHER = "other", "Boshqa"
