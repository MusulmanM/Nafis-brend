from django.contrib import admin

from .models import Product, StockEntry


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_returnable", "is_active")
    list_editable = ("price", "is_active")
    list_filter = ("is_active", "is_returnable")
    search_fields = ("name",)


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "product", "quantity", "note", "created_by")
    list_filter = ("product", "date")
    date_hierarchy = "date"
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
