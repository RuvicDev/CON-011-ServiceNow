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
print("== Agregar comentario ==")
comment_text = "Comentario agregado por validate_local.py"
add_result = client.add_comment(number, comment_text, work_note=False)
print(add_result)
print("== Confirmar que el comentario se guardó (no solo que el PATCH devolvió 200) ==")
confirmed = client.get_incident_by_number(number)
if comment_text not in (confirmed.get("comments") or ""):
    raise AssertionError(
        f"El comentario agregado no aparece al consultar el incidente {number}: "
        f"comments={confirmed.get('comments')!r}"
    )
print("Comentario confirmado en 'comments':", confirmed.get("comments"))
print("Validación ServiceNow completa. Incidente:", number)
