"""
Loyihaning asosiy sozlamalari.

Maxfiy qiymatlar (SECRET_KEY, DEBUG, ma'lumotlar bazasi parollari) kod ichida
emas, loyiha papkasidagi `.env` faylida saqlanadi. Namuna: `.env.example`.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Loyiha papkasi (manage.py turgan joy)
BASE_DIR = Path(__file__).resolve().parent.parent

# .env faylidagi qiymatlarni muhit o'zgaruvchilariga yuklaymiz
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """`.env` dagi "True"/"1"/"yes" kabi qiymatlarni bool'ga aylantiradi."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    """Vergul bilan ajratilgan qiymatlarni ro'yxatga aylantiradi."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Xavfsizlik -------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY topilmadi. `.env.example` faylidan nusxa olib `.env` yarating "
        "va SECRET_KEY qiymatini kiriting (README.md ga qarang)."
    )

DEBUG = env_bool("DEBUG", default=False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Sayt nomi (menyu, sarlavha va admin panelda ko'rinadi)
SITE_NAME = os.getenv("SITE_NAME", "Nafis")


# --- Ilovalar (app'lar) ------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Bizning app'lar
    "core",  # umumiy yordamchilar: telefon formati, so'm formati, tanlovlar
    "accounts",  # foydalanuvchilar, rollar, login
    "customers",  # mijozlar, to'lovlar (qarz)
    "inventory",  # mahsulotlar, ombor
    "orders",  # buyurtmalar, doimiy buyurtmalar
    "reports",  # hisobotlar, Excel eksport
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Umumiy shablonlar (base.html va h.k.) shu papkada turadi
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
                "core.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Ma'lumotlar bazasi -----------------------------------------------------
# Odatiy holatda SQLite. PostgreSQL'ga o'tish uchun `.env` da DB_ENGINE=postgres
# qilib, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT ni to'ldiring va
# `pip install "psycopg[binary]"` buyrug'ini bajaring.

if os.getenv("DB_ENGINE", "sqlite").lower() == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "nafis"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Foydalanuvchilar va login ---------------------------------------------

# Django'ning standart User o'rniga o'zimizning modelimiz (rol, telefon bilan)
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"  # rolga qarab yo'naltiradigan sahifa
LOGOUT_REDIRECT_URL = "accounts:login"

# Xabarlar (messages) Bootstrap klasslari bilan mos bo'lsin: error -> danger
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Til va vaqt -------------------------------------------------------------

LANGUAGE_CODE = "uz"  # o'zbek tili (lotin)
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True  # bazada UTC saqlanadi, ekranda Toshkent vaqti ko'rsatiladi


# --- Statik fayllar (CSS, JS, rasmlar) -------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # `collectstatic` shu yerga yig'adi (server uchun)


# --- Server (production) uchun xavfsizlik ---------------------------------
# DEBUG=False bo'lganda va sayt HTTPS orqali ishlaganda yoqing.

SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# Sayt nginx orqasida ishlasa: nginx "X-Forwarded-Proto: https" sarlavhasini
# yuboradi, Django esa shundan so'rov HTTPS orqali kelganini biladi.
if env_bool("BEHIND_PROXY", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
