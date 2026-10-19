"""
All deployment-specific values come from environment variables (or a
backend/.env file). Sensible development defaults are provided so the
project runs with zero configuration.
"""

from pathlib import Path

from environs import Env

env = Env()
env.read_env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Security
SECRET_KEY = env(
    "SECRET_KEY",
    "django-insecure-8i-p3%+f73hgxkzcq$f#^ch(iau4+$(3!w4m%29@)$p-!v8f!=",
)
DEBUG = env.bool("DEBUG", False)
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "https://truck-routing.onrender.com"],
)
if env("RENDER_EXTERNAL_HOSTNAME", None):  # set automatically on Render
    ALLOWED_HOSTS.append(env("RENDER_EXTERNAL_HOSTNAME"))
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", [])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "corsheaders",
    # custom apps
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


# Database MySQL is used when DATABASE_NAME is configured; otherwise
# fall back to SQLite. The routing API itself is stateless, so the
# database only backs Django admin.

if env("DATABASE_NAME", None):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DATABASE_NAME"),
            "USER": env("DATABASE_USER", ""),
            "PASSWORD": env("DATABASE_PASSWORD", ""),
            "HOST": env("DATABASE_HOST", "localhost"),
            "PORT": env("DATABASE_PORT", "3306"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Cache: external API responses (geocoding, routing, weather) are cached
# here.

REDIS_URL = env("REDIS_URL", None)
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "OPTIONS": {"MAX_ENTRIES": 20000},
        }
    }


# Password validation
_VALIDATORS = "django.contrib.auth.password_validation."
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": _VALIDATORS + "UserAttributeSimilarityValidator"},
    {"NAME": _VALIDATORS + "MinimumLengthValidator"},
    {"NAME": _VALIDATORS + "CommonPasswordValidator"},
    {"NAME": _VALIDATORS + "NumericPasswordValidator"},
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (served by WhiteNoise in production)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_INVISIBLE = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}


def _clean_origin(origin: str) -> str:
    kept = (c for c in origin if not c.isspace() and c not in _INVISIBLE)
    return "".join(kept).rstrip("/")


# The hosted frontend and local dev server are always allowed; the
# CORS_ALLOWED_ORIGINS env var only adds origins, so a malformed value
# in the hosting dashboard can't lock out the real site.
_DEFAULT_ORIGINS = [
    "https://truck-routing.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOWED_ORIGINS = list(
    dict.fromkeys(
        _DEFAULT_ORIGINS
        + [
            cleaned
            for origin in env.list("CORS_ALLOWED_ORIGINS", [])
            if (cleaned := _clean_origin(origin))
        ]
    )
)


# Django REST framework: the API is public and JSON-only.
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}


# External services. All are free and keyless by default; point these at
# self-hosted instances for production traffic.
OSRM_URL = env("OSRM_URL", "https://router.project-osrm.org")
OPEN_METEO_URL = env(
    "OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
)
PHOTON_URL = env("PHOTON_URL", "https://photon.komoot.io/api/")
HTTP_USER_AGENT = env("HTTP_USER_AGENT", "WeatherAwareTruckRouting/1.0")
HTTP_TIMEOUT_SECONDS = env.float("HTTP_TIMEOUT_SECONDS", 20.0)

# Trucks are slower than the car profile the public OSRM server uses.
TRUCK_MAX_SPEED_MPH = env.float("TRUCK_MAX_SPEED_MPH", 65.0)
OPEN_METEO_API_KEY = env("OPEN_METEO_API_KEY", "")
WEATHER_TIMEOUT_SECONDS = env.float("WEATHER_TIMEOUT_SECONDS", 45.0)
