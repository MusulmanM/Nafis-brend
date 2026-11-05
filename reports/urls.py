from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reports/", views.report, name="report"),
    path("reports/excel/", views.export_excel, name="export"),
]
