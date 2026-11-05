import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.choices import PAYMENT_METHOD_CHOICES, PaymentType
from core.forms import BootstrapFormMixin, DateInput, MoneyField
from core.templatetags.formatting import format_som

from accounts.models import User

from .models import BottlePickup, Customer


class CustomerForm(BootstrapFormMixin, forms.ModelForm):
    """Mijozni tahrirlash. Qarz va butillar bu yerda o'zgarmaydi (ular avtomatik)."""

    class Meta:
        model = Customer
        fields = [
            "name",
            "phone",
            "phone2",
            "customer_type",
            "address",
            "landmark",
            "map_url",
            "latitude",
            "longitude",
            "note",
        ]
        widgets = {"note": forms.Textarea(attrs={"rows": 2})}
        help_texts = {"map_url": "Yandex yoki Google xaritadan nusxa olingan link (ixtiyoriy)."}
        error_messages = {"phone": {"unique": "Bu telefon raqamli mijoz allaqachon mavjud."}}

    def clean(self):
        cleaned = super().clean()
        lat, lon = cleaned.get("latitude"), cleaned.get("longitude")
        if (lat is None) != (lon is None):
            raise ValidationError("Koordinatalarning ikkalasini ham kiriting yoki ikkalasini ham bo'sh qoldiring.")
        if cleaned.get("phone2") and cleaned.get("phone2") == cleaned.get("phone"):
            self.add_error("phone2", "Qo'shimcha telefon asosiy telefon bilan bir xil.")
        return cleaned


class CustomerCreateForm(CustomerForm):
    """Yangi mijoz: tizimdan oldingi qarz va butillarni bir marta kiritish mumkin."""

    class Meta(CustomerForm.Meta):
        fields = CustomerForm.Meta.fields + ["debt", "bottles"]
        labels = {"debt": "Boshlang'ich qarz (so'm)", "bottles": "Mijozdagi butillar (boshlang'ich)"}
        help_texts = {
            **CustomerForm.Meta.help_texts,
            "debt": "Mijozning tizimga kiritilgunga qadar bo'lgan qarzi.",
            "bottles": "Hozir mijozda turgan zavod butillari soni.",
        }


class PaymentForm(BootstrapFormMixin, forms.Form):
    """Mijozdan qarz to'lovini qabul qilish."""

    amount = MoneyField(label="Summa (so'm)", min_value=1)
    method = forms.ChoiceField(label="To'lov turi", choices=PAYMENT_METHOD_CHOICES, initial=PaymentType.CASH)
    date = forms.DateField(label="Sana", widget=DateInput())
    note = forms.CharField(label="Izoh", required=False, max_length=255)
    # Bir martalik kalit — ikki marta bosilganda to'lov ikki marta yozilmasligi uchun
    token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, customer, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("token", uuid.uuid4())
            self.initial.setdefault("date", timezone.localdate())
            self.initial.setdefault("amount", customer.debt or None)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount > self.customer.debt:
            raise ValidationError(f"Summa mijoz qarzidan ({format_som(self.customer.debt)}) katta bo'lmasin.")
        return amount

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise ValidationError("Kelajakdagi sanani tanlab bo'lmaydi.")
        return value


class BottleReturnForm(BootstrapFormMixin, forms.Form):
    """Mijoz butillarni o'zi olib keldi — boshliq darhol qabul qiladi."""

    quantity = forms.IntegerField(
        label="Qaytarilgan bo'sh butillar", min_value=1, widget=forms.NumberInput(attrs={"inputmode": "numeric"})
    )
    date = forms.DateField(label="Sana", widget=DateInput())
    note = forms.CharField(label="Izoh", required=False, max_length=255)
    token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, customer, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs["max"] = customer.bottles
        if not self.is_bound:
            self.initial.setdefault("token", uuid.uuid4())
            self.initial.setdefault("date", timezone.localdate())
            self.initial.setdefault("quantity", customer.bottles or None)

    def clean_quantity(self):
        value = self.cleaned_data["quantity"]
        if value > self.customer.bottles:
            raise ValidationError(f"Mijozda {self.customer.bottles} ta butil bor — undan ko'p bo'lmasin.")
        return value

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise ValidationError("Kelajakdagi sanani tanlab bo'lmaydi.")
        return value


class PickupTaskForm(BootstrapFormMixin, forms.Form):
    """Yetkazuvchiga "shu mijozdan butillarni olib kel" topshirig'i."""

    driver = forms.ModelChoiceField(
        label="Yetkazuvchi",
        queryset=User.objects.filter(role=User.Role.DRIVER, is_active=True).order_by("first_name", "username"),
        empty_label="— tanlang —",
    )
    date = forms.DateField(label="Qaysi kuni", widget=DateInput())
    note = forms.CharField(
        label="Izoh yetkazuvchi uchun",
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Masalan: kechqurun 18:00 dan keyin uyda"}),
    )
    token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, customer, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault("token", uuid.uuid4())
            self.initial.setdefault("date", timezone.localdate())

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value < timezone.localdate():
            raise ValidationError("O'tgan sanani tanlab bo'lmaydi.")
        return value

    def clean(self):
        cleaned = super().clean()
        if not self.customer.bottles:
            raise ValidationError("Bu mijozda butil yo'q.")
        if BottlePickup.objects.filter(customer=self.customer, status=BottlePickup.Status.PLANNED).exists():
            raise ValidationError("Bu mijoz uchun ochiq topshiriq allaqachon bor.")
        return cleaned
