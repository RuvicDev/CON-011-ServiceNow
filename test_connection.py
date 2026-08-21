"""Prueba de conexión estándar del conector ServiceNow."""
from __future__ import annotations

def test_connection() -> tuple[bool, str]:
    """Prueba credenciales y acceso básico a incidentes."""
    try:
        from ruvic_servicenow_connector import ServicenowAuthError, ServicenowClient, ServicenowConfigError, ServicenowDataError, ServicenowNetworkError, ServicenowSecurityError
    except ImportError:
        return False, "La librería ruvic-servicenow-connector no está instalada. Instala con: pip install git+https://github.com/tu-org/conector-servicenow.git#subdirectory=lib"
    try:
        client = ServicenowClient()
        client.ping()
    except ValueError as exc:
        return False, str(exc)
    except ServicenowConfigError as exc:
        return False, f"Configuración inválida: {exc}"
    except ServicenowAuthError as exc:
        return False, f"Autenticación o permisos ServiceNow inválidos: {exc}"
    except ServicenowNetworkError as exc:
        return False, f"Error de red hacia ServiceNow: {exc}"
    except ServicenowSecurityError as exc:
        return False, f"Bloqueo de seguridad: {exc}"
    except ServicenowDataError as exc:
        return False, f"ServiceNow rechazó la solicitud: {exc}"
    except Exception as exc:
        return False, f"Error inesperado probando ServiceNow: {exc}"
    return True, f"Conexión exitosa a ServiceNow en {client.config.base_url}."
if __name__ == "__main__":
    ok, message = test_connection(); print(f"{'OK' if ok else 'FALLO'}: {message}"); raise SystemExit(0 if ok else 1)
