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

import re
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


# Formato de número de registro ServiceNow (INC0010001, CHG0000123...). Se valida
# antes de armar sysparm_query para que no se puedan inyectar operadores (^OR, ^NQ...).
_NUMBER_RE = re.compile(r"^[A-Za-z]{2,10}\d{4,12}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]{1,80}$")
_SYS_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")

# Estados estándar de incident.state. Se aceptan el código o el nombre (inglés/español).
_STATE_CODES = {"1": "New", "2": "In Progress", "3": "On Hold", "6": "Resolved", "7": "Closed", "8": "Canceled"}
_STATE_ALIASES = {
    "new": "1", "nuevo": "1",
    "in progress": "2", "en progreso": "2", "en curso": "2",
    "on hold": "3", "en espera": "3",
    "resolved": "6", "resuelto": "6",
    "closed": "7", "cerrado": "7",
    "canceled": "8", "cancelled": "8", "cancelado": "8",
}
# Rangos válidos de los campos numéricos de prioridad.
_NUMERIC_RANGES = {"urgency": (1, 3), "impact": (1, 3), "priority": (1, 5)}


def _normalize_state(value: Any) -> str:
    text = str(value).strip()
    if text in _STATE_CODES:
        return text
    code = _STATE_ALIASES.get(text.lower())
    if code:
        return code
    valid = ", ".join(f"{code} ({name})" for code, name in _STATE_CODES.items())
    raise ServicenowDataError(f"Estado '{value}' no válido para incident.state. Valores válidos: {valid}.")


def _normalize_range(field: str, value: Any) -> str:
    low, high = _NUMERIC_RANGES[field]
    try:
        number: int | None = int(str(value).strip())
    except ValueError:
        number = None
    if number is None or not low <= number <= high:
        raise ServicenowDataError(f"{field} debe ser un número entre {low} y {high}; se recibió '{value}'.")
    return str(number)


def _normalize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Valida nombres de campo y normaliza state/urgency/impact/priority."""
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
            raise ServicenowDataError(f"Nombre de campo no válido: '{key}'.")
        if key == "state":
            normalized[key] = _normalize_state(value)
        elif key in _NUMERIC_RANGES:
            normalized[key] = _normalize_range(key, value)
        else:
            normalized[key] = value
    return normalized


def _validate_number(number: str) -> str:
    clean = (number or "").strip()
    if not clean:
        raise ServicenowDataError("number no puede estar vacío.")
    if not _NUMBER_RE.match(clean):
        raise ServicenowDataError(
            f"Número de incidente no válido: '{number}'. Usa el formato de ServiceNow, por ejemplo INC0010001."
        )
    return clean.upper()


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

    # Campos de diario: no se devuelven como columnas normales, pero son válidos al escribir.
    _JOURNAL_FIELDS = frozenset({"comments", "work_notes"})

    def _check_unknown_fields(self, keys: Any, sys_id: str | None = None) -> None:
        """Falla si algún campo no existe en la tabla incident.

        ServiceNow ignora en silencio los campos desconocidos al escribir y responde 200,
        así que antes se leen esos campos: los que no existen no vuelven en la respuesta.
        """
        wanted = [k for k in keys if k not in self._JOURNAL_FIELDS]
        if not wanted:
            return
        path = f"/incident/{sys_id}" if sys_id else "/incident"
        params: dict[str, Any] = {"sysparm_fields": ",".join(["sys_id", *wanted])}
        if not sys_id:
            params["sysparm_limit"] = 1
        data = self._request("GET", path, params=params)
        result = data.get("result") if isinstance(data, dict) else None
        record = result[0] if isinstance(result, list) and result else result
        if not isinstance(record, dict) or not record:
            return  # tabla vacía: no hay con qué comparar
        unknown = [k for k in wanted if k not in record]
        if unknown:
            raise ServicenowDataError(
                f"Campos inexistentes en la tabla incident: {', '.join(unknown)}. "
                "Revisa el nombre técnico del campo (por ejemplo short_description, state, assigned_to)."
            )

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
            "urgency": urgency,
            "impact": impact,
            **extra_fields,
        }
        if description:
            payload["description"] = description
        if priority is not None:
            payload["priority"] = priority
        payload = _normalize_fields(payload)
        self._check_unknown_fields(extra_fields.keys())
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
        number = _validate_number(number)
        params = {
            "sysparm_query": f"number={number}",
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
        fields = _normalize_fields(fields)
        if by_number:
            sys_id = self.get_incident_by_number(identifier)["sys_id"]
        else:
            sys_id = identifier.strip()
            if not _SYS_ID_RE.match(sys_id):
                raise ServicenowDataError(f"sys_id no válido: '{identifier}'. Debe tener 32 caracteres hexadecimales.")
        self._check_unknown_fields(fields.keys(), sys_id=sys_id)
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
        if not _IDENTIFIER_RE.match(table.strip()) or not _IDENTIFIER_RE.match(field.strip()):
            raise ServicenowDataError("table y field solo pueden contener letras, números y guion bajo.")
        params = {
            "sysparm_query": f"name={table.strip()}^element={field.strip()}",
            "sysparm_fields": "value,label",
        }
        data = self._request("GET", "/sys_choice", params=params)
        results = data.get("result", []) if isinstance(data, dict) else []
        self._logger.info("Choices ServiceNow consultados")
        return [dict(item) for item in results]
