from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Product(models.Model):
    """Mahsulot: 19L, 10L, 5L, 1.5L suv va h.k."""

    name = models.CharField("Nomi", max_length=100, unique=True)
    price = models.PositiveBigIntegerField("Narxi (so'm)")
    is_returnable = models.BooleanField(
        "Qaytariladigan butil",
        default=False,
        help_text="Belgilansa, bu mahsulot butili (tara) zavodga qaytariladi va "
        "mijozdagi butillar hisobiga qo'shiladi (masalan, 19L).",
    )
    is_active = models.BooleanField(
        "Faol", default=True, help_text="Faol bo'lmagan mahsulot yangi buyurtmalarda ko'rinmaydi."
    )
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ["-is_active", "-price", "name"]  # katta idishlar (19L) birinchi

    def __str__(self):
        return self.name


class StockEntry(models.Model):
    """Ombor: bir kunda ishlab chiqarilgan mahsulot miqdori.

    Ombordagi qoldiq = jami ishlab chiqarilgan − jami yetkazilgan.
    """

    date = models.DateField("Sana", default=timezone.localdate)
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="stock_entries", verbose_name="Mahsulot"
    )
    quantity = models.PositiveIntegerField(
        "Ishlab chiqarilgan soni", validators=[MinValueValidator(1)]
    )
    note = models.CharField("Izoh", max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Kiritgan",
    )
    created_at = models.DateTimeField("Kiritilgan vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Ombor yozuvi"
        verbose_name_plural = "Ombor (ishlab chiqarish)"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date:%d.%m.%Y} — {self.product}: {self.quantity} ta"
