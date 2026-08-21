"""Validación local del conector ServiceNow contra instancia real/developer."""
from __future__ import annotations
from ruvic_servicenow_connector import ServicenowClient, setup_logging
setup_logging("INFO")
client = ServicenowClient()
print("== Ping =="); print(client.ping())
print("== Crear incidente =="); inc = client.create_incident("Prueba local Ruvic ServiceNow", "Incidente creado por validate_local.py", urgency=3, impact=3); print(inc)
number = inc["number"]
print("== Consultar por número =="); print(client.get_incident_by_number(number))
print("== Actualizar incidente =="); print(client.update_incident(number, {"urgency": "2", "impact": "2"}))
print("== Agregar comentario =="); print(client.add_comment(number, "Comentario agregado por validate_local.py", work_note=False))
print("Validación ServiceNow completa. Incidente:", number)
