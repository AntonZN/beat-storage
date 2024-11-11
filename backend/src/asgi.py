import os

from django.core.asgi import get_asgi_application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.config.core")

django_application = get_asgi_application()

from src.presentation.api.routres import api_router

api = FastAPI()
api.include_router(api_router)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_pagination(api)
