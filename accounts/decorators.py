"""
Rolga qarab sahifaga kirishni cheklaydigan dekoratorlar.

Ruxsat BACKEND'da tekshiriladi: yetkazuvchi boshliq sahifasi manzilini
qo'lda yozsa ham, 403 "Ruxsat yo'q" sahifasini oladi.

Ishlatish:
    @boss_required
    def dashboard(request): ...
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import User


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("Bu sahifaga kirish huquqingiz yo'q.")
            return view_func(request, *args, **kwargs)

        # Avval tizimga kirganini, keyin rolini tekshiramiz
        return login_required(wrapper)

    return decorator


boss_required = role_required(User.Role.BOSS)
driver_required = role_required(User.Role.DRIVER)
