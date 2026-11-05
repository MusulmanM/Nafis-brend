"""Formalar uchun umumiy yordamchilar."""

from django import forms


class DateInput(forms.DateInput):
    """Brauzerning sana tanlagichi (<input type="date">).

    Bunday input faqat YYYY-MM-DD formatini tushunadi, shuning uchun formatni
    aniq ko'rsatamiz (aks holda o'zbek lokali bo'yicha 05.11.2026 bo'lib qoladi).
    """

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class BootstrapFormMixin:
    """Formadagi barcha maydonlarga Bootstrap CSS klasslarini qo'shadi.

    Ishlatish: class MyForm(BootstrapFormMixin, forms.Form): ...
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.RadioSelect, forms.HiddenInput)):
                continue
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()

    def full_clean(self):
        super().full_clean()
        # Xatosi bor maydonlar qizil chegara bilan ko'rinsin
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class MoneyField(forms.IntegerField):
    """So'mdagi summa. "125 000" kabi bo'sh joy bilan yozilsa ham qabul qiladi."""

    widget = forms.TextInput

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", 0)
        super().__init__(**kwargs)
        self.widget.attrs.setdefault("inputmode", "numeric")
        self.widget.attrs.setdefault("autocomplete", "off")

    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace(" ", "").replace("\xa0", "").replace(",", "")
        return super().to_python(value)
