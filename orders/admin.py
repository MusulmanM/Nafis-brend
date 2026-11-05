from django.contrib import admin

from .models import Order, OrderItem, RecurringOrder, RecurringOrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    autocomplete_fields = ("product",)

    # Yakunlangan (yetkazilgan, bekor qilingan...) buyurtma mahsulotlarini o'zgartirib bo'lmaydi
    def has_add_permission(self, request, obj=None):
        return obj is None or obj.is_open

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.is_open

    def has_delete_permission(self, request, obj=None):
        return obj is None or obj.is_open


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Buyurtmalar (zaxira boshqaruv).

    Holat, to'lov va butil maydonlari bu yerda faqat o'qish uchun:
    ular o'zgarganda mijoz qarzi va butil balansi ham o'zgarishi kerak,
    bu esa faqat asosiy panel orqali to'g'ri bajariladi.
    """

    list_display = (
        "id",
        "delivery_date",
        "customer",
        "driver",
        "status",
        "total_amount",
        "paid_amount",
        "payment_type",
    )
    list_filter = ("status", "delivery_date", "driver", "payment_type")
    search_fields = ("id", "customer__name", "customer__phone")
    date_hierarchy = "delivery_date"
    autocomplete_fields = ("customer",)
    list_select_related = ("customer", "driver")
    inlines = [OrderItemInline]
    readonly_fields = (
        "status",
        "total_amount",
        "payment_type",
        "paid_amount",
        "bottles_given",
        "returned_bottles",
        "fail_reason",
        "fail_note",
        "recurring",
        "created_by",
        "created_at",
        "delivered_at",
        "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("customer", "driver", "delivery_date", "note")}),
        ("Holat", {"fields": ("status", "fail_reason", "fail_note", "delivered_at")}),
        (
            "To'lov va butillar",
            {"fields": ("total_amount", "payment_type", "paid_amount", "bottles_given", "returned_bottles")},
        ),
        ("Qo'shimcha", {"fields": ("recurring", "created_by", "created_at", "updated_at")}),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and not obj.is_open:
            # Yakunlangan buyurtmada faqat izohni o'zgartirish mumkin
            fields = (*fields, "customer", "driver", "delivery_date")
        return fields

    def has_delete_permission(self, request, obj=None):
        # Yetkazilgan buyurtmani o'chirsak, mijoz qarzi/butillari noto'g'ri qolib ketadi
        if obj is not None and obj.status == Order.Status.DELIVERED:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Mahsulotlar saqlangandan keyin jami summani qayta hisoblaymiz
        if form.instance.is_open:
            form.instance.update_total()


class RecurringOrderItemInline(admin.TabularInline):
    model = RecurringOrderItem
    extra = 1
    autocomplete_fields = ("product",)


@admin.register(RecurringOrder)
class RecurringOrderAdmin(admin.ModelAdmin):
    list_display = ("customer", "weekdays_display", "driver", "is_active")
    list_filter = ("is_active", "driver")
    search_fields = ("customer__name", "customer__phone")
    autocomplete_fields = ("customer",)
    inlines = [RecurringOrderItemInline]

    @admin.display(description="Hafta kunlari")
    def weekdays_display(self, obj):
        return obj.weekdays_display()
