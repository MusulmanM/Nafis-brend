import datetime

from django.core.management import call_command
from django.test import TestCase

from customers.models import Customer
from inventory.models import Product
from orders.models import Order, RecurringOrder, RecurringOrderItem


class RecurringCommandTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(name="Ofis", phone="+998911112233", address="Yunusobod")
        product = Product.objects.create(name="19L", price=20000, is_returnable=True)
        self.rec = RecurringOrder.objects.create(customer=customer, weekdays="0,2")  # Du, Cho
        RecurringOrderItem.objects.create(recurring_order=self.rec, product=product, quantity=4)

    def test_creates_only_on_selected_days_and_never_twice(self):
        monday = "2026-11-02"
        call_command("create_recurring_orders", date=monday, days=7, stdout=open("/dev/null", "w"))
        call_command("create_recurring_orders", date=monday, days=7, stdout=open("/dev/null", "w"))
        dates = sorted(Order.objects.values_list("delivery_date", flat=True))
        self.assertEqual(dates, [datetime.date(2026, 11, 2), datetime.date(2026, 11, 4)])
        self.assertEqual(Order.objects.first().total_amount, 80000)

    def test_inactive_is_skipped(self):
        self.rec.is_active = False
        self.rec.save()
        call_command("create_recurring_orders", date="2026-11-02", stdout=open("/dev/null", "w"))
        self.assertFalse(Order.objects.exists())
