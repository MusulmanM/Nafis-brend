"""Butillarni buyurtmasiz qaytarib olish: boshliq paneli va yetkazuvchi paneli."""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from customers.models import BottlePickup, Customer
from customers.services import create_pickup

User = get_user_model()


class BossBottleTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password="x", role=User.Role.BOSS)
        self.driver = User.objects.create_user("d1", password="x", role=User.Role.DRIVER, first_name="Jasur")
        self.customer = Customer.objects.create(name="Ali", phone="+998901234567", address="Chilonzor", bottles=5)
        self.client.force_login(self.boss)
        self.today = timezone.localdate()

    def receive(self, quantity, token=None):
        return self.client.post(
            reverse("customers:bottle_return", args=[self.customer.pk]),
            {"quantity": quantity, "date": self.today.isoformat(), "note": "", "token": token or uuid.uuid4()},
        )

    def test_receive_reduces_bottles(self):
        response = self.receive("3")
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 2)
        pickup = BottlePickup.objects.get()
        self.assertEqual((pickup.status, pickup.quantity), (BottlePickup.Status.DONE, 3))

    def test_receive_double_submit_counts_once(self):
        token = uuid.uuid4()
        self.receive("2", token)
        self.receive("2", token)  # tugma ikkinchi marta bosildi
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 3)
        self.assertEqual(BottlePickup.objects.count(), 1)

    def test_cannot_receive_more_than_customer_has(self):
        response = self.receive("6")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 5)
        self.assertFalse(BottlePickup.objects.exists())

    def test_create_pickup_task_does_not_change_balance(self):
        url = reverse("customers:pickup_create", args=[self.customer.pk])
        data = {"driver": self.driver.pk, "date": self.today.isoformat(), "note": "", "token": uuid.uuid4()}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 5)
        self.assertEqual(BottlePickup.objects.get().status, BottlePickup.Status.PLANNED)

        # Ikkinchi ochiq topshiriq bermaydi
        data["token"] = uuid.uuid4()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BottlePickup.objects.count(), 1)

    def test_cancel_pickup(self):
        pickup = create_pickup(customer=self.customer, driver=self.driver, date=self.today)
        self.client.post(reverse("customers:pickup_cancel", args=[pickup.pk]))
        pickup.refresh_from_db()
        self.assertEqual(pickup.status, BottlePickup.Status.CANCELLED)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 5)

    def test_bottles_page_filters_idle_customers(self):
        Customer.objects.create(name="Vali", phone="+998901234568", address="Yunusobod", bottles=0)
        create_pickup(customer=self.customer, driver=self.driver, date=self.today)
        url = reverse("customers:bottles")
        for query in ["", "?idle=14", "?idle=30", "?idle=bad", "?q=Ali&idle=30"]:
            response = self.client.get(url + query)
            self.assertEqual(response.status_code, 200, query)
        response = self.client.get(url + "?idle=30")
        # Ali hech qachon buyurtma olmagan — "qolib ketgan" ro'yxatida
        self.assertEqual([c.name for c in response.context["page_obj"]], ["Ali"])
        self.assertEqual(response.context["totals"]["stale"]["bottles"], 5)
        self.assertContains(response, "Olib kelish topshiriqlari")

    def test_customer_page_shows_pickups(self):
        create_pickup(customer=self.customer, driver=self.driver, date=self.today)
        response = self.client.get(reverse("customers:detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Olib kelish kerak")

    def test_driver_cannot_open_boss_pages(self):
        self.client.force_login(self.driver)
        for name in ["customers:bottle_return", "customers:pickup_create"]:
            response = self.client.get(reverse(name, args=[self.customer.pk]))
            self.assertEqual(response.status_code, 403, name)


class DriverPickupTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password="x", role=User.Role.BOSS)
        self.driver = User.objects.create_user("d1", password="x", role=User.Role.DRIVER)
        self.other = User.objects.create_user("d2", password="x", role=User.Role.DRIVER)
        self.customer = Customer.objects.create(name="Ali", phone="+998901234567", address="Chilonzor", bottles=4)
        self.today = timezone.localdate()
        self.pickup = create_pickup(customer=self.customer, driver=self.driver, date=self.today, user=self.boss)
        self.prefix = f"p{self.pickup.pk}"
        self.client.force_login(self.driver)

    def done(self, quantity):
        return self.client.post(
            reverse("driver:pickup_done", args=[self.pickup.pk]), {f"{self.prefix}-quantity": quantity}
        )

    def test_today_shows_pickup(self):
        response = self.client.get(reverse("driver:today"))
        self.assertEqual(len(response.context["pickups"]), 1)
        self.assertContains(response, "Olib keldim")
        self.assertEqual(response.context["driver_remaining"], 1)

    def test_overdue_pickup_is_shown(self):
        BottlePickup.objects.filter(pk=self.pickup.pk).update(date=self.today - timedelta(days=2))
        response = self.client.get(reverse("driver:today"))
        self.assertEqual(len(response.context["pickups"]), 1)
        self.assertContains(response, "kechikkan")

    def test_done_reduces_bottles_once(self):
        self.assertRedirects(self.done("3"), reverse("driver:today"))
        self.done("3")  # ikkinchi marta bosildi
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 1)
        self.pickup.refresh_from_db()
        self.assertEqual((self.pickup.status, self.pickup.quantity), (BottlePickup.Status.DONE, 3))

        response = self.client.get(reverse("driver:my_day"))
        self.assertEqual(response.context["pickups"]["bottles"], 3)

    def test_done_validates_quantity(self):
        for value in ["0", "5", "-1", "abc"]:
            response = self.done(value)
            self.assertEqual(response.status_code, 200, value)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 4)

    def test_fail(self):
        url = reverse("driver:pickup_fail", args=[self.pickup.pk])
        response = self.client.post(url, {f"{self.prefix}-reason": "other", f"{self.prefix}-note": ""})
        self.assertEqual(response.status_code, 200)  # "Boshqa" uchun izoh majburiy
        self.client.post(url, {f"{self.prefix}-reason": "not_home", f"{self.prefix}-note": ""})
        self.pickup.refresh_from_db()
        self.assertEqual(self.pickup.status, BottlePickup.Status.FAILED)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.bottles, 4)

    def test_other_driver_gets_404(self):
        self.client.force_login(self.other)
        self.assertEqual(self.done("2").status_code, 404)
        self.assertEqual(self.client.get(reverse("driver:pickup_fail", args=[self.pickup.pk])).status_code, 404)

    def test_boss_cannot_use_driver_pages(self):
        self.client.force_login(self.boss)
        self.assertEqual(self.done("2").status_code, 403)
