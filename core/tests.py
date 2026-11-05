from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core.phone import PhoneFormField, format_phone, normalize_phone
from core.templatetags.formatting import format_som


class PhoneTests(SimpleTestCase):
    def test_normalize_various_inputs(self):
        for raw in ["+998 90 123 45 67", "998901234567", "90 123-45-67", "+998 (90) 123-45-67"]:
            self.assertEqual(normalize_phone(raw), "+998901234567", raw)

    def test_format(self):
        self.assertEqual(format_phone("+998901234567"), "+998 90 123 45 67")

    def test_form_field_rejects_bad_number(self):
        field = PhoneFormField()
        self.assertEqual(field.clean("90 123 45 67"), "+998901234567")
        with self.assertRaises(ValidationError):
            field.clean("12345")
        with self.assertRaises(ValidationError):
            field.clean("+7 999 123 45 67")


class MoneyFormatTests(SimpleTestCase):
    def test_som(self):
        self.assertEqual(format_som(125000), "125 000 so'm")
        self.assertEqual(format_som(0), "0 so'm")
        self.assertEqual(format_som(1500000), "1 500 000 so'm")
