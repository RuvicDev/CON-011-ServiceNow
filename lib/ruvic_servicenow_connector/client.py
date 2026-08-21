"""Cliente para ServiceNow Table API.

Capacidades:
- create_incident(): crear incidente.
- update_incident(): actualizar incidente por número o sys_id.
- get_incident_by_number(): consultar incidente por número.
- add_comment(): agregar comentario o work note.

El conector usa Basic Auth contra la Table API de ServiceNow. No implementa
eliminación de incidentes.
"""
from __future__ import annotations

from typing import Any

import requests
from requests import Response

from .config import ServicenowConfig
from .exceptions import ServicenowAuthError, ServicenowDataError, ServicenowNetworkError
from .logging_utils import get_logger


class ServicenowClient:
    """Cliente para gestión de incidentes en ServiceNow.

    Args:
        config: configuración opcional. Si se omite, lee RUVIC_SERVICENOW_*.

    Ejemplo:
        >>> client = ServicenowClient()
        >>> client.get_incident_by_number("INC0010001")
        {'number': 'INC0010001', 'sys_id': '...'}
    """

    def __init__(self, config: ServicenowConfig | None = None) -> None:
        self.config = config or ServicenowConfig.from_env()
        self._logger = get_logger()
        self._session = requests.Session()
        self._session.auth = (self.config.username, self.config.password)
        self._session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        clean = path if path.startswith("/") else f"/{path}"
        return self.config.base_url + clean

    def _handle_response(self, response: Response) -> Any:
        if response.status_code in {401, 403}:
            raise ServicenowAuthError(
                f"ServiceNow rechazó autenticación o permisos ({response.status_code}). "
                "Revisa usuario, contraseña y roles sobre incident."
            )
        if response.status_code == 404:
            raise ServicenowDataError("Recurso ServiceNow no encontrado. Verifica sys_id, número o endpoint.")
        if response.status_code == 429:
            raise ServicenowDataError("ServiceNow aplicó rate limiting (429). Espera y reintenta más tarde.")
        if response.status_code >= 400:
            raise ServicenowDataError(f"ServiceNow retornó HTTP {response.status_code}: {response.text[:500]}")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ServicenowDataError("ServiceNow respondió contenido no JSON cuando se esperaba JSON.") from exc

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = dict(self._session.headers)
        if extra_headers:
            headers.update(extra_headers)
        try:
            response = self._session.request(
                method=method.upper(),
                url=self._url(path),
                json=json_body,
                params={k: v for k, v in (params or {}).items() if v is not None},
                headers=headers,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
        except requests.exceptions.SSLError as exc:
            raise ServicenowNetworkError("Error SSL conectando con ServiceNow. Verifica certificado o VERIFY_SSL.") from exc
        except requests.exceptions.Timeout as exc:
            raise ServicenowNetworkError(f"Timeout conectando con ServiceNow ({self.config.timeout}s).") from exc
        except requests.exceptions.RequestException as exc:
            raise ServicenowNetworkError(f"No se pudo conectar con ServiceNow: {exc}.") from exc
        return self._handle_response(response)

    def ping(self) -> bool:
        """Verifica conexión consultando incidentes con límite mínimo.

        Returns:
            True si ServiceNow responde correctamente.
        """
        self._request("GET", "/incident", params={"sysparm_limit": 1, "sysparm_fields": "sys_id,number"})
        self._logger.info("Ping exitoso a ServiceNow")
        return True

    def create_incident(
        self,
        short_description: str,
        description: str | None = None,
        urgency: int = 3,
        impact: int = 3,
        priority: int | None = None,
        **extra_fields: Any,
    ) -> dict[str, Any]:
        """Crea un incidente en ServiceNow.

        Args:
            short_description: resumen corto del incidente.
            description: descripción detallada opcional.
            urgency: urgencia, normalmente 1 a 3.
            impact: impacto, normalmente 1 a 3.
            priority: prioridad opcional.
            extra_fields: otros campos válidos de la tabla incident.

        Returns:
            Incidente creado con `sys_id` y `number` cuando ServiceNow los retorna.
        """
        if not short_description.strip():
            raise ServicenowDataError("short_description no puede estar vacío.")
        payload: dict[str, Any] = {
            "short_description": short_description,
            "urgency": str(urgency),
            "impact": str(impact),
            **extra_fields,
        }
        if description:
            payload["description"] = description
        if priority is not None:
            payload["priority"] = str(priority)
        extra_headers = {"X-Transaction": "skip"} if self.config.skip_transaction else None
        data = self._request(
            "POST",
            "/incident",
            json_body=payload,
            params={"sysparm_fields": "sys_id,number,short_description,state,urgency,impact,priority"},
            extra_headers=extra_headers,
        )
        result = data.get("result", data) if isinstance(data, dict) else data
        self._logger.info("Incidente ServiceNow creado")
        return dict(result)

    def get_incident_by_number(self, number: str) -> dict[str, Any]:
        """Consulta un incidente por número, por ejemplo INC0010001."""
        if not number.strip():
            raise ServicenowDataError("number no puede estar vacío.")
        params = {
            "sysparm_query": f"number={number.strip()}",
            "sysparm_limit": 1,
            "sysparm_fields": "sys_id,number,short_description,description,state,urgency,impact,priority,comments,work_notes",
        }
        data = self._request("GET", "/incident", params=params)
        results = data.get("result", []) if isinstance(data, dict) else []
        if not results:
            raise ServicenowDataError(f"No se encontró incidente con número {number}.")
        self._logger.info("Incidente ServiceNow consultado por número")
        return dict(results[0])

    def update_incident(self, identifier: str, fields: dict[str, Any], by_number: bool = True) -> dict[str, Any]:
        """Actualiza un incidente por número o sys_id."""
        if not identifier.strip():
            raise ServicenowDataError("identifier no puede estar vacío.")
        if not fields:
            raise ServicenowDataError("fields no puede estar vacío.")
        sys_id = self.get_incident_by_number(identifier)["sys_id"] if by_number else identifier
        data = self._request(
            "PATCH",
            f"/incident/{sys_id}",
            json_body=fields,
            params={"sysparm_fields": "sys_id,number,short_description,state,urgency,impact,priority,comments,work_notes"},
        )
        result = data.get("result", data) if isinstance(data, dict) else data
        self._logger.info("Incidente ServiceNow actualizado")
        return dict(result)

    def add_comment(self, identifier: str, comment: str, work_note: bool = False, by_number: bool = True) -> dict[str, Any]:
        """Agrega comentario público o work note a un incidente."""
        if not comment.strip():
            raise ServicenowDataError("comment no puede estar vacío.")
        field = "work_notes" if work_note else "comments"
        return self.update_incident(identifier, {field: comment}, by_number=by_number)
