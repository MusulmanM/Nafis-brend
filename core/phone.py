"""
Telefon raqamlari bilan ishlash.

Bazada raqam bitta yagona ko'rinishda saqlanadi: "+998901234567".
Bu qidiruv va takrorlanishni tekshirishni osonlashtiradi.
Ekranda esa chiroyli ko'rinishda chiqariladi: "+998 90 123 45 67".

Foydalanuvchi raqamni istalgan ko'rinishda yozishi mumkin:
"90 123 45 67", "+998 (90) 123-45-67", "998901234567" — hammasi
avtomatik "+998901234567" ga keltiriladi.
"""

import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import models

PHONE_RE = re.compile(r"^\+998\d{9}$")
PHONE_ERROR = "Telefon raqam +998 XX XXX XX XX formatida bo'lishi kerak."


def normalize_phone(value) -> str:
    """Har xil yozilgan raqamni "+998XXXXXXXXX" ko'rinishiga keltiradi.

    Agar raqamni tanib bo'lmasa, o'zgartirmasdan qaytaradi —
    keyin `validate_phone` xato beradi.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 9:  # "901234567" — kod yozilmagan
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return text


def validate_phone(value):
    """Raqam to'g'ri formatda ekanini tekshiradi."""
    if not PHONE_RE.match(value or ""):
        raise ValidationError(PHONE_ERROR, code="invalid_phone")


def format_phone(value) -> str:
    """"+998901234567" -> "+998 90 123 45 67"."""
    if value and PHONE_RE.match(value):
        d = value[4:]
        return f"+998 {d[:2]} {d[2:5]} {d[5:7]} {d[7:]}"
    return value or ""


class PhoneFormField(forms.CharField):
    """Formalardagi telefon maydoni: kiritilgan raqamni normallashtiradi."""

    default_validators = [validate_phone]

    def __init__(self, *args, **kwargs):
        # Foydalanuvchi bo'sh joy va qavslar bilan yozishi mumkin, shuning uchun
        # forma darajasida uzunroq matnga ruxsat beramiz.
        kwargs["max_length"] = 25
        kwargs.setdefault(
            "widget",
            forms.TextInput(
                attrs={"type": "tel", "inputmode": "tel", "placeholder": "+998 90 123 45 67"}
            ),
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return normalize_phone(super().to_python(value))

    def prepare_value(self, value):
        # Formada mavjud qiymatni chiroyli ko'rinishda ko'rsatamiz
        return format_phone(value) if isinstance(value, str) else value


class PhoneField(models.CharField):
    """Model uchun telefon maydoni: doim "+998XXXXXXXXX" ko'rinishida saqlaydi."""

    default_validators = [validate_phone]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 13)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return normalize_phone(super().to_python(value))

    def formfield(self, **kwargs):
        kwargs.setdefault("form_class", PhoneFormField)
        return super().formfield(**kwargs)
