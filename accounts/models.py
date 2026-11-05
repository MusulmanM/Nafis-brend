from django.contrib.auth.models import AbstractUser
from django.db import models

from core.phone import PhoneField


class User(AbstractUser):
    """Tizim foydalanuvchisi: boshliq yoki yetkazuvchi.

    Django'ning tayyor User modelidan meros olinadi (login, parol, ism va h.k.
    tayyor). "Faol / bloklangan" uchun Django'ning `is_active` maydoni
    ishlatiladi: is_active=False bo'lsa, foydalanuvchi tizimga kira olmaydi.
    """

    class Role(models.TextChoices):
        BOSS = "boss", "Boshliq"
        DRIVER = "driver", "Yetkazuvchi"

    role = models.CharField("Rol", max_length=10, choices=Role.choices, default=Role.DRIVER)
    phone = PhoneField("Telefon", blank=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["first_name", "last_name", "username"]

    def save(self, *args, **kwargs):
        # `createsuperuser` bilan yaratilgan foydalanuvchi avtomatik boshliq bo'ladi
        if self.is_superuser:
            self.role = self.Role.BOSS
        super().save(*args, **kwargs)

    @property
    def is_boss(self) -> bool:
        return self.role == self.Role.BOSS

    @property
    def is_driver(self) -> bool:
        return self.role == self.Role.DRIVER

    def __str__(self):
        return self.get_full_name() or self.username
