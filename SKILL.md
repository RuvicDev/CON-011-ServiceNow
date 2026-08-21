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
| `RUVIC_SERVICENOW_SKIP_TRANSACTION` | Opcional. Solo pruebas/dev: `X-Transaction: skip` al crear incidentes |

Si estas variables NO existen, el conector no está configurado: no generes código que lo use; indica al usuario que lo configure en Settings → Conectores. Nunca uses variables con alias `_DEFAULT_`, `_TEST_` o `_PRODUCCION_`.

## Conexión

```python
from ruvic_servicenow_connector import ServicenowClient
client = ServicenowClient()
```

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
6. No actives `RUVIC_SERVICENOW_SKIP_TRANSACTION=true` salvo en instancia developer/de prueba con timeout interno al crear incidentes; en producción puede omitir notificaciones, eventos o reglas.
