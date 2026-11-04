---
name: servicenow
description: "Usa la librería ruvic_servicenow_connector para gestionar incidentes en ServiceNow: crear incidentes, actualizar incidentes, consultar por número y agregar comentarios. Úsala cuando el usuario pida operar incidentes ServiceNow o ITSM."
triggers:
- servicenow
- service now
- incidente
- incident
- itsm
- ticket servicenow
---

# Conector ServiceNow (ruvic_servicenow_connector)

## Regla crítica de credenciales

El código generado NUNCA hardcodea credenciales. Siempre se leen de variables de entorno:

| Variable | Contenido |
|---|---|
| `RUVIC_SERVICENOW_INSTANCE_URL` | URL de instancia ServiceNow |
| `RUVIC_SERVICENOW_USERNAME` | Usuario ServiceNow |
| `RUVIC_SERVICENOW_PASSWORD` | Contraseña ServiceNow |
| `RUVIC_SERVICENOW_VERIFY_SSL` | Verificación SSL opcional |
| `RUVIC_SERVICENOW_TIMEOUT` | Timeout opcional |
| `RUVIC_SERVICENOW_MAX_RESULTS` | Máximo de resultados |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en Settings → Conectores. Nunca uses variables con alias `_DEFAULT_`, `_TEST_` o `_PRODUCCION_`.

## Conexión

```python
from ruvic_servicenow_connector import ServicenowClient
client = ServicenowClient()
```

## Valores válidos

| Campo | Valores |
|---|---|
| `state` | 1 New, 2 In Progress, 3 On Hold, 6 Resolved, 7 Closed, 8 Canceled. Acepta el código o el nombre en inglés o español ("En progreso", "Resuelto", "Cerrado") |
| `urgency` / `impact` | 1 (alta) a 3 (baja) |
| `priority` | 1 a 5 |

- El número de incidente debe tener el formato de ServiceNow (`INC0010001`); cualquier otro texto se rechaza.
- Un estado desconocido, un valor fuera de rango o un campo que no existe en la tabla `incident` lanzan `ServicenowDataError` y no se modifica nada.
- Para resolver (6) o cerrar (7) la instancia suele exigir `close_code` y `close_notes`; consulta los códigos válidos con `client.get_choice_values("incident", "close_code")`.

## Capacidad 1 — Crear incidente

```python
incident = client.create_incident("Error de acceso", "El usuario no puede iniciar sesión")
print(incident["number"])
```

## Capacidad 2 — Consultar por número

```python
incident = client.get_incident_by_number("INC0010001")
print(incident)
```

## Capacidad 3 — Actualizar incidente

```python
updated = client.update_incident("INC0010001", {"urgency": "2", "impact": "2"})
print(updated)
```

## Capacidad 4 — Comentar incidente

```python
client.add_comment("INC0010001", "Se contactó al usuario y se está investigando", work_note=False)
```

## Buenas prácticas

1. Lee credenciales SOLO de `RUVIC_SERVICENOW_*`.
2. Nunca imprimas contraseña ni cookies/sesiones.
3. Confirma con el usuario antes de crear o actualizar incidentes reales.
4. Usa el número INC para operaciones del usuario final.
5. No implementes eliminación de incidentes; no está soportada en este conector.
6. Los valores de campos tipo choice (como `close_code`, `state`) varían entre instancias de ServiceNow — no asumas que un valor "estándar" como `Solved (Permanently)` existe en la instancia del cliente. Si una operación falla o el campo queda vacío sin error visible, confirma los valores válidos con `client.get_choice_values("incident", "close_code")` (consulta `sys_choice`) antes de reintentar.
