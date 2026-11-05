from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "get_full_name", "role", "phone", "is_active", "last_login")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "phone")

    # Tahrirlash sahifasiga rol va telefonni qo'shamiz
    fieldsets = DjangoUserAdmin.fieldsets + (("Rol va aloqa", {"fields": ("role", "phone")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Rol va aloqa", {"fields": ("first_name", "last_name", "role", "phone")}),
    )

    @admin.display(description="To'liq ismi")
    def get_full_name(self, obj):
        return obj.get_full_name()
