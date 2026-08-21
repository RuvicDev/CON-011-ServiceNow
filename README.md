# Conector ServiceNow para Ruvic

Conector Ruvic para gestión de incidentes en ServiceNow: crear incidente, actualizar incidente, consultar por número y agregar comentario.

## Capacidades

1. `create_incident(...)`.
2. `update_incident(identifier, fields, by_number=True)`.
3. `get_incident_by_number(number)`.
4. `add_comment(identifier, comment, work_note=False, by_number=True)`.

## Variables de entorno

| Variable | Obligatoria | Descripción | Default |
|---|---:|---|---|
| `RUVIC_SERVICENOW_INSTANCE_URL` | Sí | URL o subdominio ServiceNow | — |
| `RUVIC_SERVICENOW_USERNAME` | Sí | Usuario | — |
| `RUVIC_SERVICENOW_PASSWORD` | Sí | Contraseña | — |
| `RUVIC_SERVICENOW_VERIFY_SSL` | No | Verificar SSL | `true` |
| `RUVIC_SERVICENOW_TIMEOUT` | No | Timeout | `20` |
| `RUVIC_SERVICENOW_MAX_RESULTS` | No | Máximo resultados | `100` |
| `RUVIC_SERVICENOW_SKIP_TRANSACTION` | No | Envía `X-Transaction: skip` solo en creación | `false` |

## Nota sobre instancias Developer y timeouts

Algunas instancias ServiceNow Developer pueden devolver `Transaction cancelled: maximum execution time exceeded` al crear incidentes por reglas internas, SLAs o notificaciones. Para pruebas/desarrollo se puede activar `RUVIC_SERVICENOW_SKIP_TRANSACTION=true`, lo que envía el header `X-Transaction: skip` solo en `create_incident()`. No se recomienda habilitarlo por defecto en producción porque puede omitir eventos, notificaciones o reglas internas.

## Pruebas

```bash
python test_connection.py
python validate_local.py
```

## Seguridad

- Nunca subas usuario/contraseña al repositorio.
- Usa una instancia developer o usuario de prueba.
- No se implementa eliminación de incidentes.
