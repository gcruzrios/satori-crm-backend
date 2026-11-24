from __future__ import annotations

from typing import Final

ROLE_CAPABILITIES: Final[dict[str, list[str]]] = {
    "admin": [
        "users:read", "users:write", "leads:read", "leads:write", "leads:convert",
        "contacts:read", "contacts:write", "companies:read", "companies:write",
        "opportunities:read", "opportunities:write", "opportunities:move", "pipeline:read", "pipeline:move",
        "quotes:read", "quotes:write", "quotes:send", "invoices:read", "invoices:write",
        "activities:read", "activities:write", "communications:read", "communications:write",
        "services:read", "services:write", "reports:read", "audit:read",
    ],
    "manager": [
        "leads:read", "leads:write", "leads:convert", "contacts:read", "contacts:write",
        "companies:read", "companies:write", "opportunities:read", "opportunities:write",
        "opportunities:move", "pipeline:read", "pipeline:move", "quotes:read", "quotes:write", "quotes:send",
        "invoices:read", "activities:read", "activities:write", "communications:read",
        "communications:write", "services:read", "reports:read",
    ],
    "sales": [
        "leads:read", "leads:write", "leads:convert", "contacts:read", "contacts:write",
        "companies:read", "companies:write", "opportunities:read", "opportunities:write",
        "opportunities:move", "pipeline:read", "pipeline:move", "quotes:read", "quotes:write", "quotes:send",
        "invoices:read", "activities:read", "activities:write", "communications:read", "communications:write",
        "services:read",
    ],
    "therapist": [
        "activities:read", "activities:write", "contacts:read", "companies:read", "services:read",
        "communications:read",
    ],
    "accounting": [
        "invoices:read", "invoices:write", "quotes:read", "services:read", "reports:read",
    ],
}


def get_capabilities_by_role(role: str) -> list[str]:
    return ROLE_CAPABILITIES.get(role, [])
