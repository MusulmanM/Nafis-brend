from django.contrib import admin

from .models import BottlePickup, Customer, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("date", "amount", "method", "note", "received_by")
    readonly_fields = fields
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "customer_type", "address", "debt", "bottles", "created_at")
    list_filter = ("customer_type",)
    search_fields = ("name", "phone", "phone2", "address", "landmark")
    readonly_fields = ("created_at",)
    inlines = [PaymentInline]
    fieldsets = (
        (None, {"fields": ("name", "phone", "phone2", "customer_type")}),
        ("Manzil", {"fields": ("address", "landmark", "map_url", "latitude", "longitude")}),
        ("Balans", {"fields": ("debt", "bottles")}),
        ("Qo'shimcha", {"fields": ("note", "created_at")}),
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """To'lovlar faqat ko'rish uchun.

    To'lov qo'shilganda mijoz qarzi kamayishi kerak — bu ish asosiy
    boshliq panelidagi "To'lov qabul qilish" orqali bajariladi, aks holda
    qarz balansi buzilishi mumkin.
    """

    list_display = ("date", "customer", "amount", "method", "received_by", "note")
    list_filter = ("method", "date")
    search_fields = ("customer__name", "customer__phone")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BottlePickup)
class BottlePickupAdmin(admin.ModelAdmin):
    """Butil qaytarishlar faqat ko'rish uchun.

    Yozuv qo'shilsa yoki o'zgartirilsa mijozdagi butillar soni ham o'zgarishi
    kerak — bu ish boshliq panelidagi "Butillar" sahifasi orqali bajariladi.
    """

    list_display = ("date", "customer", "status", "quantity", "driver", "created_by", "note")
    list_filter = ("status", "driver", "date")
    search_fields = ("customer__name", "customer__phone")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
