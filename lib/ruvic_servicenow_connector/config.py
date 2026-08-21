"""Configuración del conector leída desde variables de entorno.

Prefijo: RUVIC_SERVICENOW_
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import ServicenowConfigError

ENV_PREFIX = "RUVIC_SERVICENOW_"


def _to_bool(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if raw == "":
        return default
    if raw in {"true", "1", "yes", "y", "on"}:
        return True
    if raw in {"false", "0", "no", "n", "off"}:
        return False
    raise ServicenowConfigError("Configuración inválida: los booleanos deben ser true/false.")


@dataclass(frozen=True)
class ServicenowConfig:
    """Parámetros para autenticar y usar ServiceNow Table API."""

    instance_url: str
    username: str
    password: str
    verify_ssl: bool = True
    timeout: int = 20
    max_results: int = 100

    @property
    def base_url(self) -> str:
        """URL base de ServiceNow Table API."""
        raw = self.instance_url.strip().rstrip("/")
        if raw.startswith("https://"):
            host_url = raw
        elif raw.startswith("http://"):
            raise ServicenowConfigError("RUVIC_SERVICENOW_INSTANCE_URL debe usar https://.")
        elif "." not in raw:
            host_url = f"https://{raw}.service-now.com"
        else:
            host_url = f"https://{raw}"
        return f"{host_url}/api/now/table"

    @classmethod
    def from_env(cls) -> "ServicenowConfig":
        """Construye la configuración desde variables RUVIC_SERVICENOW_*.

        Raises:
            ValueError: si faltan variables requeridas.
            ServicenowConfigError: si un valor opcional es inválido.
        """
        instance_url = os.environ.get(f"{ENV_PREFIX}INSTANCE_URL", "").strip()
        username = os.environ.get(f"{ENV_PREFIX}USERNAME", "").strip()
        password = os.environ.get(f"{ENV_PREFIX}PASSWORD", "").strip()
        missing = [
            name for name, value in (
                (f"{ENV_PREFIX}INSTANCE_URL", instance_url),
                (f"{ENV_PREFIX}USERNAME", username),
                (f"{ENV_PREFIX}PASSWORD", password),
            ) if not value
        ]
        if missing:
            raise ValueError(
                "Faltan variables de entorno del conector servicenow: "
                + ", ".join(missing)
                + ". Configura el conector en Settings → Conectores."
            )
        try:
            timeout = int(os.environ.get(f"{ENV_PREFIX}TIMEOUT", "20").strip() or "20")
            max_results = int(os.environ.get(f"{ENV_PREFIX}MAX_RESULTS", "100").strip() or "100")
            verify_ssl = _to_bool(os.environ.get(f"{ENV_PREFIX}VERIFY_SSL", "true"), default=True)
        except ValueError as exc:
            raise ServicenowConfigError("TIMEOUT y MAX_RESULTS deben ser enteros.") from exc
        if timeout <= 0 or timeout > 120:
            raise ServicenowConfigError("RUVIC_SERVICENOW_TIMEOUT debe estar entre 1 y 120 segundos.")
        if max_results <= 0 or max_results > 1000:
            raise ServicenowConfigError("RUVIC_SERVICENOW_MAX_RESULTS debe estar entre 1 y 1000.")
        return cls(
            instance_url=instance_url,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            timeout=timeout,
            max_results=max_results,
        )
