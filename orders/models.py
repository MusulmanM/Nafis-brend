from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone

from core.choices import FailReason, PaymentType
from customers.models import Customer
from inventory.models import Product

# Hafta kunlari. Raqamlar Python'dagi `date.weekday()` bilan bir xil: Dushanba = 0
WEEKDAYS = [
    (0, "Dushanba"),
    (1, "Seshanba"),
    (2, "Chorshanba"),
    (3, "Payshanba"),
    (4, "Juma"),
    (5, "Shanba"),
    (6, "Yakshanba"),
]
WEEKDAY_SHORT = {0: "Du", 1: "Se", 2: "Cho", 3: "Pa", 4: "Ju", 5: "Sha", 6: "Ya"}

# Faqat yetkazuvchilarni tanlash mumkin bo'lsin
DRIVER_CHOICES_FILTER = {"role": "driver"}


class Order(models.Model):
    """Buyurtma."""

    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        ON_THE_WAY = "on_way", "Yo'lda"
        DELIVERED = "delivered", "Yetkazildi"
        FAILED = "failed", "Yetkazib bo'lmadi"
        CANCELLED = "cancelled", "Bekor qilindi"

    # Sabablar core/choices.py da (butil olib kelish topshirig'ida ham ishlatiladi)
    FailReason = FailReason

    # Yetkazuvchi hali ishlay oladigan holatlar
    OPEN_STATUSES = (Status.NEW, Status.ON_THE_WAY)

    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="orders", verbose_name="Mijoz"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
        limit_choices_to=DRIVER_CHOICES_FILTER,
        verbose_name="Yetkazuvchi",
    )
    status = models.CharField(
        "Holat", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    delivery_date = models.DateField("Yetkazish sanasi", default=timezone.localdate, db_index=True)
    note = models.TextField("Izoh", blank=True)

    # --- Pul ---
    total_amount = models.PositiveBigIntegerField(
        "Jami summa (so'm)", default=0, help_text="Mahsulotlardan avtomatik hisoblanadi."
    )
    payment_type = models.CharField(
        "To'lov turi", max_length=10, choices=PaymentType.choices, blank=True
    )
    paid_amount = models.PositiveBigIntegerField("To'langan summa (so'm)", default=0)

    # --- Butillar (tara) ---
    bottles_given = models.PositiveIntegerField(
        "Berilgan butillar",
        default=0,
        help_text="Yetkazilganda mijozga berilgan qaytariladigan butillar soni.",
    )
    returned_bottles = models.PositiveIntegerField("Qaytarib olingan bo'sh butillar", default=0)

    # --- Yetkazib bo'lmasa ---
    fail_reason = models.CharField(
        "Yetkazib bo'lmadi sababi", max_length=20, choices=FailReason.choices, blank=True
    )
    fail_note = models.CharField("Sabab izohi", max_length=255, blank=True)

    # --- Qo'shimcha ---
    recurring = models.ForeignKey(
        "RecurringOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Doimiy buyurtma",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Yaratgan",
    )
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True)
    delivered_at = models.DateTimeField("Yetkazilgan vaqt", null=True, blank=True)
    updated_at = models.DateTimeField("O'zgartirilgan vaqt", auto_now=True)
    # Formadagi bir martalik kalit: "Saqlash" ikki marta bosilsa, ikkita buyurtma yaratilmaydi
    client_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        verbose_name = "Buyurtma"
        verbose_name_plural = "Buyurtmalar"
        ordering = ["-delivery_date", "-created_at"]
        constraints = [
            # Bitta doimiy buyurtmadan bir kunga faqat bitta buyurtma yaratilsin
            # (buyruq ikki marta ishga tushirilsa ham takrorlanmaydi)
            models.UniqueConstraint(
                fields=["recurring", "delivery_date"], name="unique_recurring_order_per_day"
            ),
        ]

    def __str__(self):
        return f"#{self.pk} — {self.customer.name} ({self.delivery_date:%d.%m.%Y})"

    @property
    def is_open(self) -> bool:
        """Buyurtma hali yakunlanmaganmi (yangi yoki yo'lda)."""
        return self.status in self.OPEN_STATUSES

    @property
    def debt_change(self) -> int:
        """Shu buyurtma tufayli mijoz qarzi qanchaga o'zgargani.

        Musbat — qarz oshgan, manfiy — mijoz eski qarzini ham to'lagan.
        """
        if self.status != self.Status.DELIVERED:
            return 0
        return self.total_amount - self.paid_amount

    def calculate_total(self) -> int:
        """Mahsulotlar bo'yicha jami summani hisoblaydi (saqlamaydi)."""
        result = self.items.aggregate(total=Sum(F("quantity") * F("price")))
        return result["total"] or 0

    def calculate_returnable_bottles(self) -> int:
        """Buyurtmadagi qaytariladigan butillar soni (masalan, 19L)."""
        result = self.items.filter(product__is_returnable=True).aggregate(total=Sum("quantity"))
        return result["total"] or 0

    def update_total(self):
        """Jami summani qayta hisoblab, bazaga saqlaydi."""
        self.total_amount = self.calculate_total()
        self.save(update_fields=["total_amount", "updated_at"])


class OrderItem(models.Model):
    """Buyurtmadagi bitta mahsulot qatori.

    Narx buyurtma paytida saqlanadi: keyin mahsulot narxi o'zgarsa ham
    eski buyurtmalar summasi o'zgarmaydi.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Buyurtma")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+", verbose_name="Mahsulot")
    quantity = models.PositiveIntegerField("Soni", validators=[MinValueValidator(1)])
    price = models.PositiveBigIntegerField(
        "Narxi (so'm)", blank=True, help_text="Bo'sh qoldirilsa, mahsulotning hozirgi narxi olinadi."
    )

    class Meta:
        verbose_name = "Buyurtma mahsuloti"
        verbose_name_plural = "Buyurtma mahsulotlari"
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order"),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"

    def save(self, *args, **kwargs):
        if self.price is None:
            self.price = self.product.price
        super().save(*args, **kwargs)

    @property
    def line_total(self) -> int:
        return (self.price or 0) * self.quantity


class RecurringOrder(models.Model):
    """Doimiy mijoz: belgilangan hafta kunlarida avtomatik buyurtma yaratiladi.

    Buyurtmalarni `python manage.py create_recurring_orders` buyrug'i yaratadi.
    """

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="recurring_orders", verbose_name="Mijoz"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_orders",
        limit_choices_to=DRIVER_CHOICES_FILTER,
        verbose_name="Yetkazuvchi",
        help_text="Bo'sh qoldirilsa, buyurtma yetkazuvchisiz yaratiladi.",
    )
    weekdays = models.CharField(
        "Hafta kunlari",
        max_length=20,
        validators=[
            RegexValidator(r"^[0-6](,[0-6])*$", "Hafta kunlari noto'g'ri formatda (masalan: 0,2,4).")
        ],
        help_text="Vergul bilan: 0=Dushanba ... 6=Yakshanba. Masalan: 0,2,4",
    )
    note = models.CharField("Izoh", max_length=255, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Doimiy buyurtma"
        verbose_name_plural = "Doimiy buyurtmalar"
        ordering = ["customer__name"]

    def __str__(self):
        return f"{self.customer.name} — {self.weekdays_display()}"

    def weekday_list(self) -> list[int]:
        """"0,2,4" -> [0, 2, 4]."""
        return sorted({int(d) for d in self.weekdays.split(",") if d.strip().isdigit()})

    def weekdays_display(self) -> str:
        """[0, 2, 4] -> "Du, Cho, Ju"."""
        return ", ".join(WEEKDAY_SHORT[d] for d in self.weekday_list())

    def runs_on(self, day) -> bool:
        """Shu sanada buyurtma yaratilishi kerakmi."""
        return self.is_active and day.weekday() in self.weekday_list()


class RecurringOrderItem(models.Model):
    """Doimiy buyurtmadagi mahsulot va soni."""

    recurring_order = models.ForeignKey(
        RecurringOrder, on_delete=models.CASCADE, related_name="items", verbose_name="Doimiy buyurtma"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+", verbose_name="Mahsulot")
    quantity = models.PositiveIntegerField("Soni", validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "Doimiy buyurtma mahsuloti"
        verbose_name_plural = "Doimiy buyurtma mahsulotlari"
        constraints = [
            models.UniqueConstraint(
                fields=["recurring_order", "product"], name="unique_product_per_recurring_order"
            ),
        ]

    def __str__(self):
        return f"{self.product} × {self.quantity}"
