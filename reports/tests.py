import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from customers.models import Customer
from inventory.models import Product
from orders.models import Order

User = get_user_model()


class SeedAndReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def setUp(self):
        self.client.force_login(User.objects.filter(role=User.Role.BOSS).first())

    def test_seed_demo_counts(self):
        self.assertEqual(User.objects.filter(role=User.Role.DRIVER).count(), 2)
        self.assertEqual(Customer.objects.count(), 20)
        self.assertEqual(Product.objects.count(), 3)
        days = Order.objects.values("delivery_date").distinct().count()
        self.assertEqual(days, 30)

    def test_balances_are_consistent(self):
        # Har bir mijoz qarzi = yetkazilgan (summa − to'langan) − qarz to'lovlari
        for c in Customer.objects.all():
            delivered = c.orders.filter(status=Order.Status.DELIVERED)
            expected = sum(o.total_amount - o.paid_amount for o in delivered) - sum(p.amount for p in c.payments.all())
            self.assertEqual(c.debt, expected, c.name)
            # Butillar = yetkazilgan (berilgan − qaytarilgan) − alohida olib kelinganlar
            picked = sum(p.quantity for p in c.bottle_pickups.filter(status="done"))
            bottles = sum(o.bottles_given - o.returned_bottles for o in delivered) - picked
            self.assertEqual(c.bottles, bottles, c.name)

    def test_seed_refuses_existing_data(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=io.StringIO())

    def test_report_pages(self):
        for query in ["", "?period=today", "?period=yesterday", "?period=week", "?period=last_month",
                      "?period=custom&from=2026-01-01&to=2026-12-31", "?period=custom&from=bad&to=",
                      "?period=custom&from=2020-01-01&to=2026-01-01"]:
            response = self.client.get(reverse("reports:report") + query)
            self.assertEqual(response.status_code, 200, query)
        response = self.client.get(reverse("reports:report") + "?period=month")
        self.assertGreater(response.context["counts"]["total"], 0)
        self.assertLessEqual(len(response.context["top_customers"]), 10)

    def test_excel_export(self):
        response = self.client.get(reverse("reports:export") + "?period=month")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])
        workbook = load_workbook(io.BytesIO(response.content))
        self.assertEqual(
            workbook.sheetnames,
            ["Umumiy", "To'lov turlari", "Mahsulotlar", "Yetkazuvchilar", "Top mijozlar", "Kunlik tushum", "Buyurtmalar"],
        )
        self.assertGreater(workbook["Buyurtmalar"].max_row, 1)

    def test_all_boss_pages_with_demo_data(self):
        order = Order.objects.filter(status=Order.Status.DELIVERED).first()
        customer = order.customer
        driver = User.objects.filter(role=User.Role.DRIVER).first()
        urls = [
            reverse("reports:dashboard"),
            reverse("orders:list"),
            reverse("orders:detail", args=[order.pk]),
            reverse("orders:recurring_list"),
            reverse("orders:recurring_create"),
            reverse("customers:list"),
            reverse("customers:detail", args=[customer.pk]),
            reverse("customers:debtors"),
            reverse("customers:bottles"),
            reverse("inventory:stock"),
            reverse("accounts:driver_detail", args=[driver.pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.force_login(driver)
        self.assertEqual(self.client.get(reverse("driver:today")).status_code, 200)
        self.assertEqual(self.client.get(reverse("driver:my_day")).status_code, 200)
