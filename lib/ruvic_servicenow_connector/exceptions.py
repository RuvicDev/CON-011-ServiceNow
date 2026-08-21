"""Excepciones propias del conector ServiceNow."""

class ServicenowConnectorError(Exception):
    """Error base del conector ServiceNow."""

class ServicenowConfigError(ServicenowConnectorError):
    """Falta configuración requerida o algún valor de configuración es inválido."""

class ServicenowAuthError(ServicenowConnectorError):
    """Credenciales ServiceNow inválidas o permisos insuficientes."""

class ServicenowNetworkError(ServicenowConnectorError):
    """Error de red, DNS, SSL, timeout o instancia ServiceNow no alcanzable."""

class ServicenowDataError(ServicenowConnectorError):
    """Solicitud inválida, incidente inexistente, payload inválido o límite ServiceNow alcanzado."""

class ServicenowSecurityError(ServicenowConnectorError):
    """Operación bloqueada por reglas de seguridad del conector."""
