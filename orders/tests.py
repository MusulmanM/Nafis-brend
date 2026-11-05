import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from inventory.models import Product
from orders.models import Order, OrderItem, RecurringOrder

User = get_user_model()


class OrderModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(name="Ali", phone="+998901234567", address="Chilonzor 5")
        self.big = Product.objects.create(name="19L", price=20000, is_returnable=True)
        self.small = Product.objects.create(name="1.5L", price=4000)

    def test_price_is_copied_from_product_and_total_calculated(self):
        order = Order.objects.create(customer=self.customer)
        OrderItem.objects.create(order=order, product=self.big, quantity=2)
        OrderItem.objects.create(order=order, product=self.small, quantity=3)
        order.update_total()
        self.assertEqual(order.total_amount, 2 * 20000 + 3 * 4000)
        self.assertEqual(order.calculate_returnable_bottles(), 2)

    def test_old_orders_keep_old_price(self):
        order = Order.objects.create(customer=self.customer)
        item = OrderItem.objects.create(order=order, product=self.big, quantity=1)
        self.big.price = 25000
        self.big.save()
        item.refresh_from_db()
        self.assertEqual(item.price, 20000)

    def test_customer_debt_cannot_be_negative(self):
        # Bazadagi cheklov: qarz manfiy bo'la olmaydi
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.filter(pk=self.customer.pk).update(debt=-1)


class UserRoleTests(TestCase):
    def test_superuser_becomes_boss(self):
        user = User.objects.create_superuser("admin", password="x")
        self.assertTrue(user.is_boss)

    def test_default_role_is_driver(self):
        user = User.objects.create_user("driver1", password="x")
        self.assertTrue(user.is_driver)


class RecurringOrderTests(TestCase):
    def test_runs_on_selected_weekdays(self):
        customer = Customer.objects.create(name="Ofis", phone="+998911112233", address="Yunusobod")
        rec = RecurringOrder.objects.create(customer=customer, weekdays="0,2,4")
        monday = datetime.date(2026, 11, 2)
        self.assertEqual(monday.weekday(), 0)
        self.assertTrue(rec.runs_on(monday))
        self.assertFalse(rec.runs_on(monday + datetime.timedelta(days=1)))
        self.assertEqual(rec.weekdays_display(), "Du, Cho, Ju")
        rec.is_active = False
        self.assertFalse(rec.runs_on(monday))


class OrderViewTests(TestCase):
    def setUp(self):
        self.boss = User.objects.create_user("boss", password="x", role=User.Role.BOSS)
        self.driver = User.objects.create_user("d1", password="x", role=User.Role.DRIVER, first_name="Jasur")
        self.client.force_login(self.boss)
        self.big = Product.objects.create(name="19L", price=20000, is_returnable=True)
        self.small = Product.objects.create(name="1.5L", price=4000)
        self.today = datetime.date.today()

    def data(self, **extra):
        from django.utils import timezone

        base = {
            "phone": "90 123 45 67",
            "name": "",
            "address": "",
            "landmark": "",
            "customer_type": "home",
            "driver": self.driver.pk,
            "delivery_date": timezone.localdate().isoformat(),
            "note": "",
            f"qty_{self.big.pk}": 2,
            f"qty_{self.small.pk}": 0,
        }
        base.update(extra)
        return base

    def test_create_order_with_new_customer(self):
        response = self.client.post(reverse("orders:create"), self.data(name="Yangi mijoz", address="Sergeli 1"))
        order = Order.objects.get()
        self.assertRedirects(response, reverse("orders:detail", args=[order.pk]))
        self.assertEqual(order.customer.name, "Yangi mijoz")
        self.assertEqual(order.customer.phone, "+998901234567")
        self.assertEqual(order.total_amount, 40000)
        self.assertEqual(order.driver, self.driver)

    def test_new_customer_requires_name_and_address(self):
        response = self.client.post(reverse("orders:create"), self.data())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ismini kiriting")
        self.assertFalse(Order.objects.exists())

    def test_create_order_for_existing_customer(self):
        customer = Customer.objects.create(name="Ali", phone="+998901234567", address="Chilonzor")
        self.client.post(reverse("orders:create"), self.data())
        self.assertEqual(Order.objects.get().customer, customer)
        self.assertEqual(Customer.objects.count(), 1)

    def test_order_without_products_is_rejected(self):
        response = self.client.post(reverse("orders:create"), self.data(name="A", address="B", **{f"qty_{self.big.pk}": 0}))
        self.assertContains(response, "Kamida bitta mahsulot")

    def test_double_submit_creates_one_order(self):
        import uuid

        token = str(uuid.uuid4())
        payload = self.data(name="A", address="B", token=token)
        self.client.post(reverse("orders:create"), payload)
        response = self.client.post(reverse("orders:create"), payload)
        self.assertEqual(Order.objects.count(), 1)
        self.assertRedirects(response, reverse("orders:detail", args=[Order.objects.get().pk]))

    def test_edit_cancel_and_closed_order_protection(self):
        self.client.post(reverse("orders:create"), self.data(name="A", address="B"))
        order = Order.objects.get()
        edit = self.data(**{f"qty_{self.big.pk}": 1, f"qty_{self.small.pk}": 5})
        self.client.post(reverse("orders:edit", args=[order.pk]), edit)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, 20000 + 5 * 4000)

        self.client.post(reverse("orders:cancel", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

        # Bekor qilingan buyurtmani tahrirlab ham, biriktirib ham bo'lmaydi
        self.client.post(reverse("orders:edit", args=[order.pk]), self.data(**{f"qty_{self.big.pk}": 9}))
        self.client.post(reverse("orders:assign", args=[order.pk]), {"driver": ""})
        order.refresh_from_db()
        self.assertEqual(order.total_amount, 40000)
        self.assertEqual(order.driver, self.driver)

    def test_pages_render_with_data(self):
        self.client.post(reverse("orders:create"), self.data(name="A", address="B"))
        order = Order.objects.get()
        for url in [
            reverse("orders:list"),
            reverse("orders:list") + "?overdue=1&status=new&driver=none&q=90&date=2026-02-31",
            reverse("orders:detail", args=[order.pk]),
            reverse("orders:edit", args=[order.pk]),
            reverse("customers:detail", args=[order.customer.pk]),
            reverse("accounts:driver_detail", args=[self.driver.pk]),
            reverse("reports:dashboard"),
            reverse("inventory:stock"),
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
