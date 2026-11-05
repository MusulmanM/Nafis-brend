"""Hisobotni Excel (.xlsx) fayliga yozish (openpyxl kutubxonasi bilan)."""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

MONEY = '#,##0 "so\'m"'
NUMBER = "#,##0"
HEADER_FONT = Font(bold=True)
HEADER_FILL = PatternFill("solid", fgColor="F0EFEC")
TITLE_FONT = Font(bold=True, size=14)


def _table(ws, headers, rows, formats=None, start_row=1):
    """Sarlavhali jadval yozadi. formats — har bir ustun uchun raqam formati (yoki None)."""
    for col, title in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col, value=title)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center")
    for r, row in enumerate(rows, start=start_row + 1):
        for c, value in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            if formats and formats[c - 1]:
                cell.number_format = formats[c - 1]
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    _autosize(ws)


def _autosize(ws):
    for column in ws.columns:
        width = max((len(str(cell.value)) for cell in column if cell.value is not None), default=8)
        ws.column_dimensions[get_column_letter(column[0].column)].width = min(max(width + 3, 10), 45)


def build_workbook(report: dict) -> Workbook:
    start, end = report["start"], report["end"]
    counts, money = report["counts"], report["money"]
    wb = Workbook()

    # 1) Umumiy
    ws = wb.active
    ws.title = "Umumiy"
    ws["A1"] = "Hisobot"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = f"{start:%d.%m.%Y} — {end:%d.%m.%Y}"
    summary = [
        ("Jami buyurtmalar (bekor qilinganlarsiz)", counts["total"], NUMBER),
        ("Yetkazildi", counts["delivered"], NUMBER),
        ("Yetkazib bo'lmadi", counts["failed"], NUMBER),
        ("Kutilmoqda", counts["pending"], NUMBER),
        ("Bekor qilindi", counts["cancelled"], NUMBER),
        ("Sotuv summasi", money["sales"], MONEY),
        ("Buyurtmalardan olingan pul", money["collected"], MONEY),
        ("Qarz to'lovlari", money["debt_payments"], MONEY),
        ("Jami tushum", money["received"], MONEY),
        ("Qarzga berildi", money["new_debt"], MONEY),
        ("Berilgan butillar", money["bottles_given"], NUMBER),
        ("Qaytarilgan butillar", money["bottles_returned"], NUMBER),
        ("  shundan alohida olib kelingan", money["bottles_picked"], NUMBER),
    ]
    for i, (label, value, fmt) in enumerate(summary, start=4):
        ws.cell(row=i, column=1, value=label)
        cell = ws.cell(row=i, column=2, value=value)
        cell.number_format = fmt
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 20

    # 2) To'lov turlari
    ws = wb.create_sheet("To'lov turlari")
    rows = [(r["label"], r["orders"], r["payments"], r["total"]) for r in report["payment_types"]]
    rows.append(("Qarzga berildi", money["new_debt"], None, None))
    _table(ws, ["To'lov turi", "Buyurtmalardan", "Qarz to'lovlari", "Jami"], rows, [None, MONEY, MONEY, MONEY])

    # 3) Mahsulotlar
    ws = wb.create_sheet("Mahsulotlar")
    rows = [(p["product__name"], p["sold"], p["amount"]) for p in report["products"]]
    _table(ws, ["Mahsulot", "Sotilgan soni", "Summa"], rows, [None, NUMBER, MONEY])

    # 4) Yetkazuvchilar
    ws = wb.create_sheet("Yetkazuvchilar")
    rows = [(str(d), d.delivered, d.failed, d.collected, d.cash, d.bottles_returned) for d in report["drivers"]]
    _table(
        ws,
        ["Yetkazuvchi", "Yetkazildi", "Yetkazib bo'lmadi", "Yig'ilgan pul", "Shundan naqd", "Qaytgan butil"],
        rows,
        [None, NUMBER, NUMBER, MONEY, MONEY, NUMBER],
    )

    # 5) Top mijozlar
    ws = wb.create_sheet("Top mijozlar")
    rows = [(i, c.name, c.phone, c.order_count, c.amount) for i, c in enumerate(report["top_customers"], start=1)]
    _table(ws, ["#", "Mijoz", "Telefon", "Buyurtmalar", "Yetkazilgan summa"], rows, [None, None, None, NUMBER, MONEY])

    # 6) Kunlik tushum
    ws = wb.create_sheet("Kunlik tushum")
    rows = [(day, amount) for day, amount in report["daily"]]
    _table(ws, ["Sana", "Tushum"], rows, ["DD.MM.YYYY", MONEY])

    # 7) Buyurtmalar ro'yxati
    ws = wb.create_sheet("Buyurtmalar")
    rows = [
        (
            o.pk,
            o.delivery_date,
            o.customer.name,
            o.customer.phone,
            o.customer.address,
            str(o.driver) if o.driver else "",
            o.get_status_display(),
            o.total_amount,
            o.get_payment_type_display() if o.payment_type else "",
            o.paid_amount,
            o.returned_bottles,
        )
        for o in report["orders"]
    ]
    _table(
        ws,
        ["#", "Sana", "Mijoz", "Telefon", "Manzil", "Yetkazuvchi", "Holat", "Jami", "To'lov turi", "To'langan", "Qaytgan butil"],
        rows,
        [None, "DD.MM.YYYY", None, None, None, None, None, MONEY, None, MONEY, NUMBER],
    )
    return wb
