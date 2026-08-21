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

## Pruebas

```bash
python test_connection.py
python validate_local.py
```

## Seguridad

- Nunca subas usuario/contraseña al repositorio.
- Usa una instancia developer o usuario de prueba.
- No se implementa eliminación de incidentes.

## Limitaciones conocidas

- Si una instancia developer gratuita falla por timeout en la primera petición, es normal (arranque en frío) — reintenta la petición; no es un problema del conector.
- Los valores de campos tipo choice (como `close_code`, `state`) varían entre instancias de ServiceNow. No asumas que un valor "estándar" (por ejemplo `Solved (Permanently)`) existe en la instancia del cliente: ServiceNow puede descartar en silencio un valor de choice inválido y dejar el campo vacío, lo que luego puede disparar un error de Data Policy por campo obligatorio faltante. Confirma los valores válidos con `client.get_choice_values(table, field)` antes de usarlos.
