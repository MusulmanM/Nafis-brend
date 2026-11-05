"""
Test (demo) ma'lumotlar yaratish — hisobotlarni darhol ko'rish uchun.

    python manage.py seed_demo            # bo'sh bazaga
    python manage.py seed_demo --reset    # mavjud buyurtma/mijoz/ombor ma'lumotlarini O'CHIRIB, qaytadan

Yaratiladi: 2 ta yetkazuvchi, 20 ta mijoz, 3 ta mahsulot, 30 kunlik buyurtmalar,
qarz to'lovlari, ombor yozuvlari, 3 ta doimiy buyurtma va butil olib kelish
topshiriqlari (bugungilari yetkazuvchi panelida ko'rinadi).

Hamma narsa asosiy servislar orqali yaratiladi (create_order, mark_delivered, ...),
shuning uchun qarz va butil balanslari saytdagidek to'g'ri hisoblanadi.
"""

import random
import uuid
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from core.choices import PaymentType
from customers.models import BottlePickup, Customer, Payment
from customers.services import accept_payment, complete_pickup, create_pickup, fail_pickup, receive_bottles
from inventory.models import Product, StockEntry
from orders.models import Order, RecurringOrder, RecurringOrderItem
from orders.recurring import create_recurring_orders
from orders.services import cancel_order, create_order, mark_delivered, mark_failed, start_delivery

DRIVER_PASSWORD = "parol123"

DRIVERS = [
    ("jasur", "Jasur", "Karimov", "+998901112233"),
    ("bekzod", "Bekzod", "Aliyev", "+998935554433"),
]

PRODUCTS = [("19L", 20000, True), ("5L", 9000, False), ("1.5L", 4000, False)]

CUSTOMERS = [
    ("Aziz Rahimov", "home"),
    ("Dilnoza Yusupova", "home"),
    ("\"Mega Savdo\" MChJ", "office"),
    ("Sherzod Toshev", "home"),
    ("Malika Qodirova", "home"),
    ("IT Park ofisi", "office"),
    ("Ravshan Ergashev", "home"),
    ("Nodira Sobirova", "home"),
    ("Akmal Nurmatov", "home"),
    ("\"Oq Yo'l\" logistika", "office"),
    ("Gulnora Hasanova", "home"),
    ("Bobur Mirzayev", "home"),
    ("Kamola Ismoilova", "home"),
    ("\"Med Line\" klinikasi", "office"),
    ("Otabek Saidov", "home"),
    ("Zarina Abdullayeva", "home"),
    ("Farrux Jo'rayev", "home"),
    ("\"Ilm\" o'quv markazi", "office"),
    ("Sevara Normatova", "home"),
    ("\"Baraka\" restorani", "office"),
]

STREETS = [
    "Chilonzor tumani, 9-kvartal, 12-uy",
    "Yunusobod tumani, 4-mavze, 33-uy",
    "Amir Temur ko'chasi, 108",
    "Sergeli tumani, 7-mavze, 21-uy",
    "Mirzo Ulug'bek tumani, Buyuk Ipak Yo'li 45",
    "Olmazor tumani, Sebzor 14",
    "Yakkasaroy tumani, Shota Rustaveli 30",
    "Shayxontohur tumani, Navoiy ko'chasi 17",
    "Mirobod tumani, Taras Shevchenko 9",
    "Yashnobod tumani, Mahtumquli 72",
]

LANDMARKS = ["Korzinka yonida", "maktab ro'parasida", "metro yonida", "dorixona yonida", "", "", ""]


class Command(BaseCommand):
    help = "Hisobotlarni ko'rish uchun test ma'lumotlar yaratadi (2 yetkazuvchi, 20 mijoz, 3 mahsulot, 30 kun)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Necha kunlik buyurtmalar (odatda 30).")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="DIQQAT: avval barcha buyurtma, mijoz, to'lov, ombor va mahsulot yozuvlarini o'chiradi.",
        )
        parser.add_argument("--seed", type=int, default=42, help="Tasodifiy sonlar boshlang'ich qiymati.")

    def handle(self, *args, **options):
        if not 1 <= options["days"] <= 365:
            raise CommandError("--days 1 dan 365 gacha bo'lishi kerak.")
        has_data = Customer.objects.exists() or Order.objects.exists() or Product.objects.exists()
        if has_data and not options["reset"]:
            raise CommandError(
                "Bazada allaqachon ma'lumot bor. Hammasini o'chirib, demo ma'lumot yaratish uchun:\n"
                "    python manage.py seed_demo --reset"
            )
        self.rng = random.Random(options["seed"])
        with transaction.atomic():
            if options["reset"]:
                self.reset()
            self.create(options["days"])

    # ------------------------------------------------------------------

    def reset(self):
        Order.objects.all().delete()
        RecurringOrder.objects.all().delete()
        Payment.objects.all().delete()
        BottlePickup.objects.all().delete()
        Customer.objects.all().delete()
        StockEntry.objects.all().delete()
        Product.objects.all().delete()
        User.objects.filter(username__in=[d[0] for d in DRIVERS]).delete()
        self.stdout.write("Eski ma'lumotlar o'chirildi.")

    def create(self, days):
        rng = self.rng
        today = timezone.localdate()

        boss = User.objects.filter(role=User.Role.BOSS).first()
        if boss is None:
            boss = User.objects.create_superuser("admin", password="admin12345", first_name="Boshliq")
            self.stdout.write("Boshliq yaratildi: admin / admin12345")

        drivers = []
        for username, first, last, phone in DRIVERS:
            driver = User.objects.create_user(
                username, password=DRIVER_PASSWORD, first_name=first, last_name=last, phone=phone, role=User.Role.DRIVER
            )
            drivers.append(driver)

        products = {name: Product.objects.create(name=name, price=price, is_returnable=ret) for name, price, ret in PRODUCTS}
        p19, p5, p15 = products["19L"], products["5L"], products["1.5L"]

        customers = []
        phones = rng.sample(range(1000000, 9999999), len(CUSTOMERS))
        for i, (name, ctype) in enumerate(CUSTOMERS):
            has_coords = i % 3 == 0
            customers.append(
                Customer.objects.create(
                    name=name,
                    phone=f"+99890{phones[i]:07d}",
                    address=rng.choice(STREETS),
                    landmark=rng.choice(LANDMARKS),
                    customer_type=ctype,
                    latitude=round(rng.uniform(41.25, 41.36), 6) if has_coords else None,
                    longitude=round(rng.uniform(69.18, 69.34), 6) if has_coords else None,
                )
            )
        # Ba'zi mijozlar tez-tez buyurtma beradi
        weights = [rng.choice([1, 1, 2, 3, 5]) for _ in customers]
        # Ikki uy mijozi ~3 hafta oldin buyurtma berishni to'xtatgan — butillari
        # ularda "qolib ketgan" (Butillar sahifasidagi filtrni ko'rish uchun)
        self.churned = set(rng.sample([c for c in customers if c.customer_type == "home"], 2))
        self.churn_day = today - timedelta(days=20)

        offices = [c for c in customers if c.customer_type == "office"]
        plans = [
            (offices[0], "0,2,4", drivers[0], {p19: 4}),
            (offices[1], "1,3,5", drivers[1], {p19: 3}),
            (offices[2], "0,3", drivers[0], {p19: 6, p15: 12}),
        ]
        for customer, weekdays, driver, items in plans:
            rec = RecurringOrder.objects.create(customer=customer, weekdays=weekdays, driver=driver, note="Doimiy mijoz")
            for product, qty in items.items():
                RecurringOrderItem.objects.create(recurring_order=rec, product=product, quantity=qty)

        first_day = today - timedelta(days=days - 1)
        for offset in range(days):
            day = first_day + timedelta(days=offset)
            self.create_day(day, today, boss, drivers, customers, weights, products)

        self.stdout.write(self.style.SUCCESS("Demo ma'lumotlar tayyor:"))
        self.stdout.write(f"  Yetkazuvchilar: {', '.join(d.username for d in drivers)} (parol: {DRIVER_PASSWORD})")
        self.stdout.write(f"  Mijozlar: {Customer.objects.count()}, mahsulotlar: {Product.objects.count()}")
        self.stdout.write(f"  Buyurtmalar: {Order.objects.count()} ({days} kun), qarz to'lovlari: {Payment.objects.count()}")
        self.stdout.write(f"  Butil qaytarishlar: {BottlePickup.objects.count()}")

    def create_day(self, day, today, boss, drivers, customers, weights, products):
        rng = self.rng
        p19, p5, p15 = products["19L"], products["5L"], products["1.5L"]

        # Ombor: kunlik ishlab chiqarish
        for product, low, high in [(p19, 45, 70), (p5, 8, 20), (p15, 40, 80)]:
            StockEntry.objects.create(date=day, product=product, quantity=rng.randint(low, high), created_by=boss)

        # Doimiy buyurtmalar + oddiy buyurtmalar
        orders = create_recurring_orders(day, user=boss)["created"]
        chosen = set()
        for _ in range(rng.randint(5, 9)):
            chosen.add(rng.choices(customers, weights=weights)[0])
        if day < self.churn_day:
            if day.toordinal() % 3 == 0:
                chosen |= self.churned
        else:
            chosen -= self.churned
        for customer in chosen:
            items = {p19: rng.choice([1, 1, 2, 2, 3])}
            if rng.random() < 0.25:
                items[p15] = rng.choice([6, 12])
            if rng.random() < 0.15:
                items[p5] = rng.choice([1, 2, 4])
            driver = rng.choice(drivers) if (day < today or rng.random() < 0.85) else None
            orders.append(create_order(customer=customer, items=items, delivery_date=day, driver=driver, user=boss))

        for order in orders:
            created = timezone.make_aware(datetime.combine(day, time(rng.randint(7, 9), rng.randint(0, 59))))
            Order.objects.filter(pk=order.pk).update(created_at=created)
            if order.driver is None:
                if day < today:
                    order.driver = rng.choice(drivers)
                    Order.objects.filter(pk=order.pk).update(driver=order.driver)
                else:
                    continue  # bugungi yetkazuvchisiz buyurtma qoladi
            self.finish(order, day, today)

        self.create_pickups(day, today, boss, drivers)

        # Ba'zi kunlari qarzdorlardan to'lov
        if day < today and rng.random() < 0.6:
            debtors = list(Customer.objects.filter(debt__gt=0))
            for customer in rng.sample(debtors, min(len(debtors), rng.randint(1, 2))):
                amount = min(customer.debt, rng.choice([20000, 40000, 50000, 100000]))
                accept_payment(
                    customer=customer,
                    amount=amount,
                    method=rng.choice(["cash", "cash", "card", "click", "payme"]),
                    date=day,
                    note="",
                    user=boss,
                    client_token=uuid.uuid4(),
                )

    def create_pickups(self, day, today, boss, drivers):
        """Butillarni buyurtmasiz qaytarib olish: topshiriqlar va mijoz o'zi olib kelganlari."""
        rng = self.rng
        busy = BottlePickup.objects.filter(status=BottlePickup.Status.PLANNED).values("customer")
        candidates = [
            c for c in Customer.objects.filter(bottles__gte=2).exclude(pk__in=busy) if c not in self.churned
        ]
        if not candidates:
            return
        if day == today:
            # Bugun har bir yetkazuvchiga bittadan ochiq topshiriq (panelda ko'rinadi)
            for driver, customer in zip(drivers, rng.sample(candidates, min(len(drivers), len(candidates)))):
                create_pickup(customer=customer, driver=driver, date=day, note="Bo'sh butillarni olib keling", user=boss)
            return
        roll = rng.random()
        if roll < 0.2:
            customer = rng.choice(candidates)
            pickup = create_pickup(customer=customer, driver=rng.choice(drivers), date=day, user=boss)
            if rng.random() < 0.85:
                at = timezone.make_aware(datetime.combine(day, time(rng.randint(10, 18), rng.randint(0, 59))))
                complete_pickup(pickup, driver=pickup.driver, quantity=rng.randint(1, customer.bottles), at=at)
            else:
                fail_pickup(pickup, driver=pickup.driver, reason=Order.FailReason.NOT_HOME)
        elif roll < 0.3:
            customer = rng.choice(candidates)
            receive_bottles(
                customer=customer,
                quantity=rng.randint(1, customer.bottles),
                date=day,
                note="",
                user=boss,
                client_token=uuid.uuid4(),
            )

    def finish(self, order, day, today):
        """Buyurtmani tasodifiy natija bilan yakunlaydi (bugungilarning bir qismi ochiq qoladi)."""
        rng = self.rng
        roll = rng.random()
        if day == today:
            if roll < 0.45:
                pass  # pastda yetkaziladi
            elif roll < 0.6:
                start_delivery(order, order.driver)
                return
            else:
                return  # "yangi" bo'lib qoladi
        elif roll > 0.94:
            cancel_order(order)
            return
        elif roll > 0.86:
            reason = rng.choice(list(Order.FailReason.values))
            mark_failed(order, driver=order.driver, reason=reason, note="Ertaga qayta urinish" if reason == "other" else "")
            return

        order.refresh_from_db()
        customer = Customer.objects.get(pk=order.customer_id)
        total = order.total_amount
        pay = rng.random()
        if pay < 0.5:
            payment_type, paid = PaymentType.CASH, total
        elif pay < 0.65:
            payment_type, paid = PaymentType.CARD, total
        elif pay < 0.75:
            payment_type, paid = PaymentType.CLICK, total
        elif pay < 0.84:
            payment_type, paid = PaymentType.PAYME, total
        elif pay < 0.93:
            payment_type, paid = PaymentType.DEBT, 0
        else:
            payment_type, paid = PaymentType.CASH, total // 2 // 1000 * 1000  # qisman to'lov
        # Ba'zan mijoz eski qarzini ham beradi
        if payment_type != PaymentType.DEBT and customer.debt and rng.random() < 0.3:
            paid += min(customer.debt, 20000)

        given = order.calculate_returnable_bottles()
        returned = min(given, customer.bottles)
        if returned and rng.random() < 0.1:
            returned -= 1  # bitta butilni keyinroq qaytaradi
        delivered_at = timezone.make_aware(datetime.combine(day, time(rng.randint(9, 18), rng.randint(0, 59))))
        if day == today:
            delivered_at = min(delivered_at, timezone.now())
        mark_delivered(
            order,
            driver=order.driver,
            payment_type=payment_type,
            paid_amount=paid,
            returned_bottles=returned,
            at=delivered_at,
        )
