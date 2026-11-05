import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer, Payment

User = get_user_model()


class PaymentTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password="x", role=User.Role.BOSS)
        self.client.force_login(self.boss)
        self.customer = Customer.objects.create(name="Ali", phone="+998901234567", address="Chilonzor", debt=50000)
        self.url = reverse("customers:payment", args=[self.customer.pk])

    def post(self, amount, token):
        return self.client.post(
            self.url,
            {"amount": amount, "method": "cash", "date": timezone.localdate().isoformat(), "note": "", "token": token},
        )

    def test_payment_reduces_debt(self):
        response = self.post("20 000", uuid.uuid4())
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt, 30000)
        self.assertEqual(Payment.objects.count(), 1)

    def test_double_submit_counts_once(self):
        token = uuid.uuid4()
        self.post("20000", token)
        self.post("20000", token)  # tugma ikkinchi marta bosildi
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt, 30000)
        self.assertEqual(Payment.objects.count(), 1)

    def test_amount_greater_than_debt_is_rejected(self):
        response = self.post("60000", uuid.uuid4())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "katta bo")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt, 50000)

    def test_negative_and_empty_amount_rejected(self):
        for bad in ["-100", "0", "", "abc"]:
            response = self.post(bad, uuid.uuid4())
            self.assertEqual(response.status_code, 200, bad)
        self.assertEqual(Payment.objects.count(), 0)


class CustomerLookupTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("boss", password="x", role=User.Role.BOSS))
        Customer.objects.create(name="Vali", phone="+998901234567", address="Yunusobod", debt=15000)

    def test_lookup_found_and_not_found(self):
        url = reverse("customers:lookup")
        data = self.client.get(url, {"phone": "90 123 45 67"}).json()
        self.assertTrue(data["found"])
        self.assertEqual(data["name"], "Vali")
        self.assertEqual(data["debt_display"], "15 000 so'm")
        data = self.client.get(url, {"phone": "+998 91 000 00 00"}).json()
        self.assertEqual(data, {"found": False, "valid": True})
        data = self.client.get(url, {"phone": "123"}).json()
        self.assertFalse(data["valid"])

    def test_duplicate_phone_rejected_on_create(self):
        response = self.client.post(
            reverse("customers:create"),
            {"name": "Boshqa", "phone": "901234567", "customer_type": "home", "address": "X", "debt": 0, "bottles": 0},
        )
        self.assertContains(response, "allaqachon mavjud")
