"""Lightweight Service Bus configuration shared by API and worker."""
from __future__ import annotations

import os
from typing import Any

_VALID_MODES = {"inline", "service_bus", "disabled"}


def execution_mode() -> str:
    """Return the explicit Labs execution mode."""
    mode = os.environ.get(
        "PRAXYS_LABS_EXECUTION_MODE",
        "inline",
    ).strip().lower()
    if mode not in _VALID_MODES:
        raise RuntimeError(
            "PRAXYS_LABS_EXECUTION_MODE must be inline, service_bus, "
            "or disabled"
        )
    return mode


def service_bus_namespace() -> str:
    """Return the configured fully-qualified Service Bus namespace."""
    return os.environ.get(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "",
    ).strip()


def service_bus_queue() -> str:
    """Return the configured Service Bus queue name."""
    return os.environ.get(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "",
    ).strip()


def validate_configuration() -> None:
    """Fail fast when isolated execution is selected without its queue."""
    if execution_mode() != "service_bus":
        return
    namespace = service_bus_namespace()
    missing = [
        name
        for name, value in (
            ("PRAXYS_LABS_SERVICE_BUS_FQDN", namespace),
            ("PRAXYS_LABS_SERVICE_BUS_QUEUE", service_bus_queue()),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Labs Service Bus configuration is incomplete: "
            + ", ".join(missing)
        )
    if (
        not namespace.endswith(".servicebus.windows.net")
        or "://" in namespace
        or "/" in namespace
        or ":" in namespace
        or any(character.isspace() for character in namespace)
    ):
        raise RuntimeError(
            "PRAXYS_LABS_SERVICE_BUS_FQDN must be a hostname without "
            "a scheme, path, or port"
        )


def azure_credential() -> Any:
    """Return the effective managed identity credential for Service Bus."""
    service_bus_client_id = os.environ.get(
        "PRAXYS_LABS_SERVICE_BUS_CLIENT_ID",
        "",
    ).strip()
    if service_bus_client_id:
        from azure.identity import ManagedIdentityCredential

        return ManagedIdentityCredential(client_id=service_bus_client_id)
    if os.environ.get("WEBSITE_SITE_NAME"):
        from azure.identity import ManagedIdentityCredential

        return ManagedIdentityCredential()
    client_id = os.environ.get("AZURE_CLIENT_ID", "").strip()
    if client_id:
        from azure.identity import ManagedIdentityCredential

        return ManagedIdentityCredential(client_id=client_id)
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()
