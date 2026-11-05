from urllib.parse import quote

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.choices import PAYMENT_METHOD_CHOICES, FailReason, PaymentType
from core.phone import PhoneField


class Customer(models.Model):
    """Mijoz (uy yoki ofis).

    `debt` (qarz) va `bottles` (mijozdagi zavod butillari) maydonlari qo'lda
    emas, buyurtma yetkazilganda va to'lov qabul qilinganda avtomatik
    yangilanadi (bu mantiq keyingi bosqichlarda `services.py` fayllarida).
    """

    class Type(models.TextChoices):
        HOME = "home", "Uy"
        OFFICE = "office", "Ofis"

    name = models.CharField("Ism", max_length=150)
    phone = PhoneField("Telefon", unique=True)
    phone2 = PhoneField("Qo'shimcha telefon", blank=True)
    address = models.CharField("Manzil", max_length=255)
    landmark = models.CharField("Mo'ljal (orientir)", max_length=255, blank=True)
    map_url = models.URLField("Xarita linki", max_length=500, blank=True)
    latitude = models.DecimalField(
        "Kenglik (latitude)",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "Uzunlik (longitude)",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    customer_type = models.CharField("Turi", max_length=10, choices=Type.choices, default=Type.HOME)
    note = models.TextField("Izoh", blank=True)
    debt = models.PositiveBigIntegerField(
        "Qarz (so'm)", default=0, help_text="Avtomatik hisoblanadi. Qo'lda faqat tuzatish uchun o'zgartiring."
    )
    bottles = models.PositiveIntegerField(
        "Mijozdagi butillar",
        default=0,
        help_text="Mijozda turgan zavod butillari soni. Avtomatik hisoblanadi.",
    )
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def yandex_maps_url(self) -> str:
        """Yandex xaritada ochish uchun link."""
        if self.map_url:
            return self.map_url
        if self.has_coordinates:
            return f"https://yandex.uz/maps/?pt={self.longitude},{self.latitude}&z=17&l=map"
        return f"https://yandex.uz/maps/?text={quote(self.address)}"

    def google_maps_url(self) -> str:
        """Google xaritada ochish uchun link."""
        if self.has_coordinates:
            return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
        if self.map_url:
            return self.map_url
        return f"https://www.google.com/maps/search/?api=1&query={quote(self.address)}"


class Payment(models.Model):
    """Mijozning eski qarzini to'lashi.

    Buyurtma yetkazilgandagi to'lov `Order.paid_amount` da saqlanadi;
    bu model esa alohida qarz to'lovlari uchun.
    """

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="payments", verbose_name="Mijoz"
    )
    amount = models.PositiveBigIntegerField("Summa (so'm)", validators=[MinValueValidator(1)])
    date = models.DateField("Sana", default=timezone.localdate)
    method = models.CharField(
        "To'lov turi", max_length=10, choices=PAYMENT_METHOD_CHOICES, default=PaymentType.CASH
    )
    note = models.CharField("Izoh", max_length=255, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Qabul qilgan",
    )
    created_at = models.DateTimeField("Kiritilgan vaqt", auto_now_add=True)
    # Formadagi bir martalik kalit: tugma ikki marta bosilsa, ikkinchi so'rov
    # shu kalit takrorlangani uchun bazaga yozilmaydi (ikki marta hisoblanmaydi)
    client_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar (qarz)"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.customer.name}: {self.amount} so'm ({self.date:%d.%m.%Y})"


class BottlePickup(models.Model):
    """Mijozdan bo'sh butillarni BUYURTMASIZ qaytarib olish.

    Mijoz buyurtma bermay qo'ysa yoki ortiqcha butil to'planib qolsa, butillar
    unda qolib ketmasligi uchun. Ikki xil yoziladi:
      * topshiriq — boshliq yetkazuvchiga "shu mijozdan butillarni olib kel"
        deydi (holati "olib kelish kerak"), yetkazuvchi o'z panelida bajaradi;
      * darhol — mijoz butillarni o'zi zavodga olib keldi, boshliq yozib qo'yadi.

    Mijozdagi butillar soni (`Customer.bottles`) faqat "olib kelindi" holatida
    kamayadi — bu ish `customers/services.py` dagi funksiyalarda.
    `date` — rejadagi sana, bajarilgandan keyin esa haqiqatda olib kelingan kun.
    """

    class Status(models.TextChoices):
        PLANNED = "planned", "Olib kelish kerak"
        DONE = "done", "Olib kelindi"
        FAILED = "failed", "Bo'lmadi"
        CANCELLED = "cancelled", "Bekor qilindi"

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="bottle_pickups", verbose_name="Mijoz"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bottle_pickups",
        limit_choices_to={"role": "driver"},
        verbose_name="Yetkazuvchi",
    )
    date = models.DateField("Sana", default=timezone.localdate, db_index=True)
    status = models.CharField(
        "Holat", max_length=10, choices=Status.choices, default=Status.PLANNED, db_index=True
    )
    quantity = models.PositiveIntegerField("Olib kelingan butillar", default=0)
    note = models.CharField("Izoh", max_length=255, blank=True)
    fail_reason = models.CharField("Bo'lmadi sababi", max_length=20, choices=FailReason.choices, blank=True)
    fail_note = models.CharField("Sabab izohi", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Kiritgan",
    )
    created_at = models.DateTimeField("Kiritilgan vaqt", auto_now_add=True)
    done_at = models.DateTimeField("Olib kelingan vaqt", null=True, blank=True)
    updated_at = models.DateTimeField("O'zgartirilgan vaqt", auto_now=True)
    # Ikki marta bosilganda ikki marta yozilmasligi uchun bir martalik kalit
    client_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        verbose_name = "Butil qaytarish"
        verbose_name_plural = "Butil qaytarishlar"
        ordering = ["-date", "-created_at"]
        constraints = [
            # Bitta mijozga bir vaqtda faqat bitta ochiq topshiriq
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(status="planned"),
                name="one_open_pickup_per_customer",
            ),
        ]

    def __str__(self):
        return f"{self.customer.name}: {self.get_status_display()} ({self.date:%d.%m.%Y})"

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.PLANNED
