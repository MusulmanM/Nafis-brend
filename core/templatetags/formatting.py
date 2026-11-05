"""
Shablonlar uchun formatlash filtrlari.

Ishlatish (shablon boshida):  {% load formatting %}
    {{ order.total_amount|som }}     -> 125 000 so'm
    {{ customer.debt|num }}          -> 125 000
    {{ customer.phone|phone }}       -> +998 90 123 45 67
"""

from django import template
from django.utils import timezone
from django.utils.html import format_html

from core.phone import format_phone

register = template.Library()


def format_number(value) -> str:
    """125000 -> "125 000" (minglar bo'sh joy bilan ajratiladi)."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return "0"
    return f"{number:,}".replace(",", " ")


def format_som(value) -> str:
    """125000 -> "125 000 so'm"."""
    return f"{format_number(value)} so'm"


@register.filter
def num(value):
    return format_number(value)


@register.filter
def som(value):
    return format_som(value)


@register.filter
def phone(value):
    return format_phone(value)


@register.filter
def status_class(status):
    """Buyurtma holati uchun CSS klass (rangli nuqta): {{ order.status|status_class }}."""
    return f"status-{status}"


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """Joriy URL parametrlarini saqlab, ba'zilarini almashtiradi.

    Sahifalashda filtrlar yo'qolmasligi uchun:  ?{% url_replace page=2 %}
    """
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.filter(name="abs")
def absolute(value):
    """Modul (manfiy belgisiz): {{ -5000|abs }} -> 5000."""
    try:
        return abs(value)
    except TypeError:
        return value


@register.filter
def som_stat(value):
    """KPI plitkasi uchun: katta raqam + kichik "so'm" (telefonda raqam ikkiga bo'linmaydi)."""
    return format_html('<span class="text-nowrap">{}</span> <span class="stat-unit">so\'m</span>', format_number(value))


@register.filter
def days_ago(value) -> str:
    """Sana/vaqt necha kun oldin bo'lgani: "bugun", "kecha", "12 kun oldin"."""
    if not value:
        return ""
    if hasattr(value, "tzinfo"):  # datetime -> Toshkent vaqtidagi sana
        value = timezone.localdate(value) if timezone.is_aware(value) else value.date()
    days = (timezone.localdate() - value).days
    if days <= 0:
        return "bugun"
    if days == 1:
        return "kecha"
    return f"{days} kun oldin"
