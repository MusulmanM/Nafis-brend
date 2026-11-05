from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.forms import BootstrapFormMixin, DateInput, MoneyField

from .models import Product, StockEntry


class StockEntryForm(BootstrapFormMixin, forms.ModelForm):
    """Kunlik ishlab chiqarishni kiritish."""

    class Meta:
        model = StockEntry
        fields = ["date", "product", "quantity", "note"]
        widgets = {"date": DateInput(), "quantity": forms.NumberInput(attrs={"inputmode": "numeric", "min": 1})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["product"].empty_label = "— tanlang —"

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise ValidationError("Kelajakdagi sanani tanlab bo'lmaydi.")
        return value


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    price = MoneyField(label="Narxi (so'm)", min_value=1)

    class Meta:
        model = Product
        fields = ["name", "price", "is_returnable", "is_active"]
        error_messages = {"name": {"unique": "Bunday nomli mahsulot allaqachon bor."}}
