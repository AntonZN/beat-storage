import os

import environ

from .base import *
from .ldap import *  # noqa: F401, F403

env = environ.Env(DEBUG=bool)
environ.Env.read_env(BASE_DIR / "../.env")

DEBUG = env("DEBUG", default=True)
USE_POSTGRES = env("USE_POSTGRES", default=False)
SECRET_KEY = env("SECRET_KEY", default="beats")

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = [
    env("CSRF_TRUSTED_ORIGINS"),
]

REDIS_HOST = "redis://127.0.0.1:6379"
STATIC_ROOT = os.path.join(BASE_DIR, "../static/")

if USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "SCHEME": env("POSTGRES_SCHEME"),
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": None,
            "DISABLE_SERVER_SIDE_CURSORS": True,
            "OPTIONS": {},
        }
    }

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_PUBLIC_MEDIA_LOCATION = "media"

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="storage")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="http://minio:9000")
AWS_S3_CUSTOM_DOMAIN = env(
    "AWS_S3_CUSTOM_DOMAIN", default=f"localhost:9000/{AWS_STORAGE_BUCKET_NAME}"
)

STORAGES = {
    "default": {
        "BACKEND": "src.config.backends.s3.PublicMediaStorage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            "endpoint_url": AWS_S3_ENDPOINT_URL,
            "querystring_auth": False,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
