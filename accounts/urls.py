from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Yetkazuvchilar (boshliq uchun)
    path("drivers/", views.driver_list, name="driver_list"),
    path("drivers/new/", views.driver_create, name="driver_create"),
    path("drivers/<int:pk>/", views.driver_detail, name="driver_detail"),
    path("drivers/<int:pk>/edit/", views.driver_edit, name="driver_edit"),
    path("drivers/<int:pk>/toggle/", views.driver_toggle_active, name="driver_toggle"),
]
