"""
Doimiy mijozlar uchun buyurtmalarni avtomatik yaratish.

Ishlatish:
    python manage.py create_recurring_orders                  # bugun uchun
    python manage.py create_recurring_orders --date 2026-11-10
    python manage.py create_recurring_orders --days 3         # bugun, ertaga, indinga

Har kuni ertalab avtomatik ishlatish (Linux cron, Windows Task Scheduler) — README.md da.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date

from orders.recurring import create_recurring_orders


class Command(BaseCommand):
    help = "Doimiy buyurtmalardan kerakli kunlar uchun buyurtmalar yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Boshlanish sanasi (YYYY-MM-DD). Odatda — bugun.")
        parser.add_argument("--days", type=int, default=1, help="Necha kun uchun yaratish (odatda 1).")

    def handle(self, *args, **options):
        start = timezone.localdate()
        if options["date"]:
            try:
                start = parse_date(options["date"])
            except ValueError:
                start = None
            if start is None:
                raise CommandError("Sana YYYY-MM-DD formatida bo'lishi kerak, masalan: 2026-11-10")
        if not 1 <= options["days"] <= 31:
            raise CommandError("--days 1 dan 31 gacha bo'lishi kerak.")

        total = 0
        for i in range(options["days"]):
            day = start + timedelta(days=i)
            result = create_recurring_orders(day)
            total += len(result["created"])
            self.stdout.write(
                f"{day:%d.%m.%Y}: {len(result['created'])} ta yaratildi, "
                f"{result['existing']} ta avvaldan bor, {result['skipped']} ta o'tkazib yuborildi"
            )
        self.stdout.write(self.style.SUCCESS(f"Jami yaratildi: {total} ta buyurtma"))
