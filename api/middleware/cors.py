"""REFINET Cloud — CORS Configuration"""

from fastapi.middleware.cors import CORSMiddleware
from api.config import get_settings


def add_cors(app):
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-REFINET-Signature"],
    )
