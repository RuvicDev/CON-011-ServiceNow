"""Cliente para ServiceNow Table API.

Capacidades:
- create_incident(): crear incidente.
- update_incident(): actualizar incidente por número o sys_id.
- get_incident_by_number(): consultar incidente por número.
- add_comment(): agregar comentario o work note.
- get_choice_values(): consultar valores válidos de un campo choice (ej. close_code).

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

# Indicios en el cuerpo de un 401/403 de que el rechazo es por una regla de negocio
# (Data Policy, Business Rule, ACL, campo obligatorio) y no por autenticación.
_DATA_POLICY_INDICATORS = (
    "data policy",
    "business rule",
    "mandatory",
    "obligatorio",
    "required field",
    "campo requerido",
    "acl",
    "access control",
)

# Indicios de que el rechazo sí es por credenciales, token o usuario.
_AUTH_INDICATORS = (
    "invalid credentials",
    "invalid username or password",
    "user is not active",
    "authentication failed",
    "not authenticated",
    "login failure",
    "user not authorized to login",
)


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

    def _extract_error_message(self, response: Response) -> str:
        """Extrae el mensaje de error real del cuerpo de respuesta de ServiceNow."""
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or ""
                detail = error.get("detail") or ""
                combined = " ".join(part for part in (message, detail) if part)
                if combined:
                    return combined
        return response.text[:500]

    def _handle_response(self, response: Response) -> Any:
        if response.status_code in {401, 403}:
            error_text = self._extract_error_message(response)
            lowered = error_text.lower()
            is_data_policy = any(keyword in lowered for keyword in _DATA_POLICY_INDICATORS)
            is_auth = any(keyword in lowered for keyword in _AUTH_INDICATORS)
            if response.status_code == 403 and is_data_policy and not is_auth:
                raise ServicenowDataError(
                    "ServiceNow rechazó la operación por una regla de negocio "
                    f"(Data Policy/Business Rule/ACL), no por autenticación: {error_text}"
                )
            raise ServicenowAuthError(
                f"ServiceNow rechazó autenticación o permisos ({response.status_code}): {error_text}"
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
    ) -> Any:
        try:
            response = self._session.request(
                method=method.upper(),
                url=self._url(path),
                json=json_body,
                params={k: v for k, v in (params or {}).items() if v is not None},
                headers=dict(self._session.headers),
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
        data = self._request(
            "POST",
            "/incident",
            json_body=payload,
            params={"sysparm_fields": "sys_id,number,short_description,state,urgency,impact,priority"},
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
            "sysparm_display_value": "true",
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
            params={
                "sysparm_fields": "sys_id,number,short_description,state,urgency,impact,priority,comments,work_notes",
                "sysparm_display_value": "true",
            },
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

    def get_choice_values(self, table: str, field: str) -> list[dict[str, str]]:
        """Consulta en sys_choice los valores válidos de un campo choice en esta instancia.

        Los valores de campos choice (por ejemplo incident.close_code o incident.state)
        varían entre instancias ServiceNow: no asumas que un valor "estándar" existe.
        """
        if not table.strip() or not field.strip():
            raise ServicenowDataError("table y field no pueden estar vacíos.")
        params = {
            "sysparm_query": f"name={table.strip()}^element={field.strip()}",
            "sysparm_fields": "value,label",
        }
        data = self._request("GET", "/sys_choice", params=params)
        results = data.get("result", []) if isinstance(data, dict) else []
        self._logger.info("Choices ServiceNow consultados")
        return [dict(item) for item in results]
