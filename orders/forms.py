import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from core.choices import PaymentType
from core.forms import BootstrapFormMixin, DateInput, MoneyField
from core.phone import PhoneFormField
from core.templatetags.formatting import format_som
from customers.models import Customer
from inventory.models import Product

from .models import WEEKDAYS, Order

MAX_QUANTITY = 1000  # bitta mahsulotdan bir buyurtmada eng ko'pi


def active_drivers():
    return User.objects.filter(role=User.Role.DRIVER, is_active=True).order_by("first_name", "username")


class ProductQuantitiesMixin:
    """Har bir mahsulot uchun "qty_<id>" nomli son maydonini qo'shadi.

    Buyurtma formasida ham, doimiy buyurtma formasida ham ishlatiladi.
    """

    def add_product_fields(self, existing: dict[int, int]):
        """existing — {mahsulot_id: soni} (tahrirlashda oldingi qiymatlar)."""
        self.products = list(
            Product.objects.filter(Q(is_active=True) | Q(pk__in=existing)).order_by("-price", "name")
        )
        for product in self.products:
            self.fields[f"qty_{product.pk}"] = forms.IntegerField(
                label=product.name,
                min_value=0,
                max_value=MAX_QUANTITY,
                required=False,
                initial=existing.get(product.pk, 0),
            )

    def product_rows(self):
        """Shablon uchun: [(mahsulot, son maydoni), ...]."""
        return [(product, self[f"qty_{product.pk}"]) for product in self.products]

    def collect_items(self, cleaned) -> dict:
        """Soni 0 dan katta mahsulotlar: {mahsulot: soni}. Bo'sh bo'lsa — xato."""
        items = {}
        for product in self.products:
            quantity = cleaned.get(f"qty_{product.pk}") or 0
            if quantity > 0:
                items[product] = quantity
        if not items:
            self.add_error(None, "Kamida bitta mahsulot sonini kiriting.")
        return items


class OrderForm(ProductQuantitiesMixin, BootstrapFormMixin, forms.Form):
    """Yangi buyurtma yaratish yoki tahrirlash.

    Yangi buyurtmada mijoz telefon raqami bo'yicha topiladi. Topilmasa,
    shu formadagi ism va manzil bilan yangi mijoz yaratiladi.
    """

    CUSTOMER_FIELDS = ("phone", "name", "address", "landmark", "customer_type")

    # --- Mijoz (faqat yangi buyurtmada) ---
    phone = PhoneFormField(label="Mijoz telefoni")
    name = forms.CharField(label="Ism", max_length=150, required=False)
    address = forms.CharField(label="Manzil", max_length=255, required=False)
    landmark = forms.CharField(label="Mo'ljal", max_length=255, required=False)
    customer_type = forms.ChoiceField(
        label="Turi", choices=Customer.Type.choices, initial=Customer.Type.HOME, required=False
    )

    # --- Buyurtma ---
    driver = forms.ModelChoiceField(
        label="Yetkazuvchi",
        queryset=User.objects.none(),
        required=False,
        empty_label="— keyinroq biriktiriladi —",
    )
    delivery_date = forms.DateField(label="Yetkazish sanasi", widget=DateInput())
    note = forms.CharField(label="Izoh", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    # Bir martalik kalit — "Saqlash" ikki marta bosilsa, ikkita buyurtma yaratilmaydi
    token = forms.UUIDField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        self.customer = order.customer if order else None
        self.items = {}
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = active_drivers()

        existing = {}
        if order:
            # Tahrirlashda mijoz o'zgarmaydi
            for name in self.CUSTOMER_FIELDS:
                del self.fields[name]
            existing = {item.product_id: item.quantity for item in order.items.all()}
        self.add_product_fields(existing)

        if not self.is_bound:
            if order:
                self.initial.update(driver=order.driver_id, delivery_date=order.delivery_date, note=order.note)
            else:
                self.initial.setdefault("delivery_date", timezone.localdate())
                self.initial.setdefault("token", uuid.uuid4())

    def clean_delivery_date(self):
        value = self.cleaned_data["delivery_date"]
        unchanged = self.order is not None and value == self.order.delivery_date
        if value < timezone.localdate() and not unchanged:
            raise ValidationError("O'tib ketgan sanani tanlab bo'lmaydi.")
        return value

    def clean(self):
        cleaned = super().clean()
        # Mijozni telefon bo'yicha topamiz (faqat yangi buyurtmada)
        if self.order is None and cleaned.get("phone"):
            self.customer = Customer.objects.filter(phone=cleaned["phone"]).first()
            if self.customer is None:
                if not cleaned.get("name", "").strip():
                    self.add_error("name", "Yangi mijozning ismini kiriting.")
                if not cleaned.get("address", "").strip():
                    self.add_error("address", "Yangi mijozning manzilini kiriting.")
        self.items = self.collect_items(cleaned)
        return cleaned

    def new_customer_data(self) -> dict:
        data = self.cleaned_data
        return {
            "phone": data["phone"],
            "name": data["name"].strip(),
            "address": data["address"].strip(),
            "landmark": data.get("landmark", "").strip(),
            "customer_type": data.get("customer_type") or Customer.Type.HOME,
        }


class RecurringOrderForm(ProductQuantitiesMixin, BootstrapFormMixin, forms.Form):
    """Doimiy buyurtma: mijoz, hafta kunlari, mahsulotlar."""

    phone = PhoneFormField(label="Mijoz telefoni", help_text="Mijoz avval tizimga qo'shilgan bo'lishi kerak.")
    weekdays = forms.TypedMultipleChoiceField(
        label="Hafta kunlari", choices=WEEKDAYS, coerce=int, widget=forms.CheckboxSelectMultiple
    )
    driver = forms.ModelChoiceField(
        label="Yetkazuvchi", queryset=User.objects.none(), required=False, empty_label="— biriktirilmasin —"
    )
    note = forms.CharField(label="Izoh", required=False, max_length=255)
    is_active = forms.BooleanField(label="Faol", required=False, initial=True)

    def __init__(self, *args, recurring=None, **kwargs):
        self.recurring = recurring
        self.customer = recurring.customer if recurring else None
        self.items = {}
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = active_drivers()
        existing = {}
        if recurring:
            del self.fields["phone"]
            existing = {item.product_id: item.quantity for item in recurring.items.all()}
            if not self.is_bound:
                self.initial.update(
                    weekdays=recurring.weekday_list(),
                    driver=recurring.driver_id,
                    note=recurring.note,
                    is_active=recurring.is_active,
                )
        self.add_product_fields(existing)

    def clean(self):
        cleaned = super().clean()
        if self.recurring is None and cleaned.get("phone"):
            self.customer = Customer.objects.filter(phone=cleaned["phone"]).first()
            if self.customer is None:
                self.add_error("phone", "Bu raqamli mijoz topilmadi. Avval mijozni qo'shing.")
        self.items = self.collect_items(cleaned)
        return cleaned

    def weekdays_value(self) -> str:
        """[0, 2, 4] -> "0,2,4" (modelda shunday saqlanadi)."""
        return ",".join(str(d) for d in sorted(set(self.cleaned_data["weekdays"])))


class DeliveryForm(BootstrapFormMixin, forms.Form):
    """Yetkazuvchi "Yetkazib berdim" bosganda to'ldiradigan forma."""

    payment_type = forms.ChoiceField(
        label="To'lov turi", choices=PaymentType.choices, initial=PaymentType.CASH, widget=forms.RadioSelect
    )
    paid_amount = MoneyField(label="Olingan summa (so'm)", required=False)
    returned_bottles = forms.IntegerField(
        label="Qaytarib olingan bo'sh butillar",
        min_value=0,
        max_value=MAX_QUANTITY,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )

    def __init__(self, *args, order, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)
        customer = order.customer
        self.bottles_given = order.calculate_returnable_bottles()
        self.max_paid = order.total_amount + customer.debt
        self.max_returned = customer.bottles + self.bottles_given
        self.fields["returned_bottles"].widget.attrs["max"] = self.max_returned
        if not self.is_bound:
            self.initial.setdefault("paid_amount", order.total_amount)
            # Odatda mijoz nechta to'la butil olsa, shuncha bo'shini qaytaradi (agar bo'lsa)
            self.initial.setdefault("returned_bottles", min(self.bottles_given, customer.bottles))

    def clean(self):
        cleaned = super().clean()
        payment_type = cleaned.get("payment_type")
        paid = cleaned.get("paid_amount") or 0
        if payment_type == PaymentType.DEBT:
            cleaned["paid_amount"] = 0
        elif payment_type:
            if paid <= 0:
                self.add_error("paid_amount", "Olingan summani kiriting yoki \"Qarzga\" ni tanlang.")
            elif paid > self.max_paid:
                self.add_error(
                    "paid_amount", f"Juda katta. Buyurtma + eski qarz = {format_som(self.max_paid)}."
                )
            cleaned["paid_amount"] = paid
        returned = cleaned.get("returned_bottles")
        if returned is not None and returned > self.max_returned:
            self.add_error("returned_bottles", f"Mijozda bu buyurtma bilan birga {self.max_returned} ta butil bo'ladi.")
        return cleaned


class FailForm(BootstrapFormMixin, forms.Form):
    """"Yetkazib bo'lmadi" — sabab tanlanadi."""

    reason = forms.ChoiceField(label="Sabab", choices=Order.FailReason.choices, widget=forms.RadioSelect)
    note = forms.CharField(label="Izoh", required=False, max_length=255)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == Order.FailReason.OTHER and not cleaned.get("note", "").strip():
            self.add_error("note", "\"Boshqa\" tanlanganda sababni yozing.")
        return cleaned


class PickupDoneForm(BootstrapFormMixin, forms.Form):
    """Yetkazuvchi butil olib kelish topshirig'ini bajarganda: nechta olib keldi."""

    quantity = forms.IntegerField(
        label="Olib kelingan bo'sh butillar",
        min_value=1,
        max_value=MAX_QUANTITY,
        widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
    )

    def __init__(self, *args, pickup, **kwargs):
        self.pickup = pickup
        super().__init__(*args, **kwargs)
        self.max_quantity = pickup.customer.bottles
        self.fields["quantity"].widget.attrs["max"] = self.max_quantity
        if not self.is_bound:
            self.initial.setdefault("quantity", self.max_quantity or None)

    def clean_quantity(self):
        value = self.cleaned_data["quantity"]
        if value > self.max_quantity:
            raise ValidationError(f"Mijozda {self.max_quantity} ta butil bor — undan ko'p bo'lmasin.")
        return value
