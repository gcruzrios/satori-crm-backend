from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.activities import router as activities_router
from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.communications import router as communications_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.health import router as health_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.leads import router as leads_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.pipelines import router as pipelines_router
from app.api.v1.quotes import router as quotes_router
from app.api.v1.search import router as search_router
from app.api.v1.services import router as services_router
from app.api.v1.users import router as users_router
from app.api.v1.webhooks import router as webhooks_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Satori CRM API",
        version="2.0.0",
        description="Backend del CRM Clínicas Satori según la especificación final.",
    )

    # CORS. The frontend sends credentials (httpOnly refresh cookie), so the
    # response must echo the caller's Origin — `allow_origins=["*"]` together
    # with `allow_credentials=True` makes browsers reject every credentialed
    # response. Set CORS_ORIGINS (comma-separated) to lock this down in
    # production; otherwise any origin is reflected.
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    cors_kwargs: dict = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if cors_origins:
        cors_kwargs["allow_origins"] = cors_origins
    else:
        cors_kwargs["allow_origin_regex"] = ".*"
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(leads_router, prefix="/api/v1")
    app.include_router(contacts_router, prefix="/api/v1")
    app.include_router(companies_router, prefix="/api/v1")
    app.include_router(services_router, prefix="/api/v1")
    app.include_router(pipelines_router, prefix="/api/v1")
    app.include_router(opportunities_router, prefix="/api/v1")
    app.include_router(quotes_router, prefix="/api/v1")
    app.include_router(invoices_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(communications_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")
    return app


app = create_app()
