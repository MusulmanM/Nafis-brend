"""Yetkazuvchi paneli: balans yangilanishi, ruxsatlar, ikki marta bosish."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from inventory.models import Product
from orders.models import Order
from orders.services import create_order

User = get_user_model()


class DriverPanelTests(TestCase):
    def setUp(self):
        self.driver = User.objects.create_user("d1", password="x", role=User.Role.DRIVER)
        self.other = User.objects.create_user("d2", password="x", role=User.Role.DRIVER)
        self.big = Product.objects.create(name="19L", price=20000, is_returnable=True)
        self.small = Product.objects.create(name="1.5L", price=4000)
        self.customer = Customer.objects.create(
            name="Ali", phone="+998901234567", address="Chilonzor", debt=10000, bottles=2
        )
        self.order = create_order(
            customer=self.customer,
            items={self.big: 2, self.small: 3},  # 52 000 so'm, 2 ta butil
            delivery_date=timezone.localdate(),
            driver=self.driver,
        )
        self.client.force_login(self.driver)
        self.prefix = f"o{self.order.pk}"

    def deliver(self, payment_type="cash", paid="52000", returned="2"):
        return self.client.post(
            reverse("driver:deliver", args=[self.order.pk]),
            {
                f"{self.prefix}-payment_type": payment_type,
                f"{self.prefix}-paid_amount": paid,
                f"{self.prefix}-returned_bottles": returned,
            },
        )

    def test_today_page_shows_only_my_orders(self):
        create_order(customer=self.customer, items={self.big: 1}, delivery_date=timezone.localdate(), driver=self.other)
        response = self.client.get(reverse("driver:today"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["open_orders"]), 1)
        self.assertContains(response, "tel:+998901234567")
        self.assertContains(response, "Yetkazib berdim")

    def test_start_then_deliver_updates_balances(self):
        self.client.post(reverse("driver:start", args=[self.order.pk]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.ON_THE_WAY)

        response = self.deliver(paid="40000", returned="1")
        self.assertRedirects(response, reverse("driver:today"))
        self.order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERED)
        self.assertEqual(self.order.bottles_given, 2)
        self.assertEqual(self.customer.debt, 10000 + 52000 - 40000)  # qarz 12 000 ga oshdi
        self.assertEqual(self.customer.bottles, 2 + 2 - 1)

    def test_double_click_counts_once(self):
        self.deliver(payment_type="debt", paid="0")
        self.deliver(payment_type="debt", paid="0")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt, 10000 + 52000)
        self.assertEqual(self.customer.bottles, 2)

    def test_paying_old_debt_too(self):
        self.deliver(paid="62000")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.debt, 0)

    def test_invalid_amounts_rejected(self):
        for paid, returned in [("70000", "2"), ("-5", "2"), ("0", "2"), ("52000", "9"), ("52000", "-1")]:
            response = self.deliver(paid=paid, returned=returned)
            self.assertEqual(response.status_code, 200, (paid, returned))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.NEW)

    def test_cannot_touch_other_drivers_order(self):
        self.client.force_login(self.other)
        self.assertEqual(self.deliver().status_code, 404)
        self.assertEqual(self.client.post(reverse("driver:start", args=[self.order.pk])).status_code, 404)

    def test_fail_requires_note_for_other(self):
        url = reverse("driver:fail", args=[self.order.pk])
        response = self.client.post(url, {f"{self.prefix}-reason": "other", f"{self.prefix}-note": ""})
        self.assertEqual(response.status_code, 200)
        self.client.post(url, {f"{self.prefix}-reason": "no_answer", f"{self.prefix}-note": ""})
        self.order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.FAILED)
        self.assertEqual(self.customer.debt, 10000)  # balans o'zgarmadi

    def test_my_day(self):
        self.deliver(paid="52000")
        response = self.client.get(reverse("driver:my_day"))
        self.assertEqual(response.context["money"]["cash"], 52000)
        self.assertEqual(response.context["money"]["count"], 1)

    def test_boss_cannot_open_driver_panel(self):
        self.client.force_login(User.objects.create_user("b", password="x", role=User.Role.BOSS))
        self.assertEqual(self.client.get(reverse("driver:today")).status_code, 403)
