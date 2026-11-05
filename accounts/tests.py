from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AdminSmokeTests(TestCase):
    """Django admin panelidagi barcha sahifalar xatosiz ochilishini tekshiradi."""

    def setUp(self):
        self.admin = User.objects.create_superuser("boss", password="parol12345")
        self.client.force_login(self.admin)

    def test_admin_pages_open(self):
        models = [
            "accounts_user",
            "customers_customer",
            "customers_payment",
            "inventory_product",
            "inventory_stockentry",
            "orders_order",
            "orders_recurringorder",
        ]
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        for name in models:
            url = reverse(f"admin:{name}_changelist")
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for name in ["accounts_user", "customers_customer", "inventory_product", "orders_order"]:
            url = reverse(f"admin:{name}_add")
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_customer_phone_is_normalized_via_admin(self):
        from customers.models import Customer

        response = self.client.post(
            reverse("admin:customers_customer_add"),
            {
                "name": "Vali",
                "phone": "90 123 45 67",
                "phone2": "",
                "customer_type": "home",
                "address": "Sergeli 3",
                "debt": 0,
                "bottles": 0,
                "payments-TOTAL_FORMS": 0,
                "payments-INITIAL_FORMS": 0,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.get().phone, "+998901234567")


class RoleAccessTests(TestCase):
    """Rollar bo'yicha ruxsatlar backend'da tekshirilishini sinaydi."""

    BOSS_PAGES = [
        "reports:dashboard",
        "orders:list",
        "orders:create",
        "customers:list",
        "customers:create",
        "customers:debtors",
        "customers:bottles",
        "inventory:stock",
        "inventory:product_list",
        "accounts:driver_list",
        "accounts:driver_create",
        "orders:recurring_list",
        "orders:recurring_create",
        "reports:report",
        "reports:export",
    ]

    def setUp(self):
        self.boss = User.objects.create_user("boss", password="parol12345", role=User.Role.BOSS)
        self.driver = User.objects.create_user("haydovchi", password="parol12345", role=User.Role.DRIVER)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("reports:dashboard"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('reports:dashboard')}")

    def test_driver_gets_403_on_boss_pages(self):
        self.client.force_login(self.driver)
        for name in self.BOSS_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_boss_pages_open(self):
        self.client.force_login(self.boss)
        for name in self.BOSS_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_login_redirects_by_role(self):
        response = self.client.post(reverse("accounts:login"), {"username": "boss", "password": "parol12345"}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], reverse("reports:dashboard"))
        self.client.logout()
        response = self.client.post(
            reverse("accounts:login"), {"username": "haydovchi", "password": "parol12345"}, follow=True
        )
        self.assertEqual(response.redirect_chain[-1][0], reverse("driver:today"))

    def test_blocked_driver_cannot_login(self):
        self.driver.is_active = False
        self.driver.save()
        response = self.client.post(reverse("accounts:login"), {"username": "haydovchi", "password": "parol12345"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bloklangan")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_boss_creates_and_blocks_driver(self):
        self.client.force_login(self.boss)
        response = self.client.post(
            reverse("accounts:driver_create"),
            {
                "first_name": "Sardor",
                "last_name": "",
                "phone": "93 111 22 33",
                "username": "sardor",
                "password1": "Kuchli-parol-77",
                "password2": "Kuchli-parol-77",
            },
        )
        driver = User.objects.get(username="sardor")
        self.assertRedirects(response, reverse("accounts:driver_detail", args=[driver.pk]))
        self.assertTrue(driver.is_driver)
        self.assertEqual(driver.phone, "+998931112233")
        self.client.post(reverse("accounts:driver_toggle", args=[driver.pk]))
        driver.refresh_from_db()
        self.assertFalse(driver.is_active)
