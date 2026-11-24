from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.deps import require_access
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

    # CORS: the frontend sends credentials (httpOnly refresh cookie), so only the
    # explicitly allowed origins (CORS_ORIGINS, comma-separated) are accepted.
    cors_origins = [o.strip().rstrip("/") for o in get_settings().cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public: health check, login, provider webhooks. Everything else requires a
    # valid bearer token plus the capability for the resource (see core/deps.py).
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")

    protected = [
        (users_router, "users"),
        (leads_router, "leads"),
        (contacts_router, "contacts"),
        (companies_router, "companies"),
        (services_router, "services"),
        (pipelines_router, "opportunities"),
        (opportunities_router, "opportunities"),
        (quotes_router, "quotes"),
        (invoices_router, "invoices"),
        (activities_router, "activities"),
        (communications_router, "communications"),
        (notifications_router, None),  # any authenticated user (scoped to own rows)
        (search_router, None),
    ]
    for router, resource in protected:
        app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_access(resource))])
    return app


app = create_app()
