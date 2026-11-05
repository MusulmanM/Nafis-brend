from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from core.forms import BootstrapFormMixin

from .models import User


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Login yoki parol noto'g'ri (yoki akkaunt bloklangan).",
        "inactive": "Akkaunt bloklangan.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Login"
        self.fields["username"].widget.attrs.update({"autocapitalize": "none", "autocomplete": "username"})
        self.fields["password"].label = "Parol"


class DriverCreateForm(BootstrapFormMixin, UserCreationForm):
    """Yangi yetkazuvchi qo'shish (login va parol bilan)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "username"]
        labels = {"username": "Login (tizimga kirish uchun)"}
        help_texts = {"username": "Lotin harflari, raqamlar va @/./+/-/_ belgilari."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["phone"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.DRIVER
        if commit:
            user.save()
        return user


class DriverUpdateForm(BootstrapFormMixin, forms.ModelForm):
    """Yetkazuvchi ma'lumotlarini tahrirlash. Parol ixtiyoriy: bo'sh qolsa o'zgarmaydi."""

    new_password = forms.CharField(
        label="Yangi parol",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Parolni o'zgartirmoqchi bo'lmasangiz, bo'sh qoldiring.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "username"]
        labels = {"username": "Login"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["phone"].required = True
        self.fields["username"].help_text = ""

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
            validate_password(password, self.instance)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user
