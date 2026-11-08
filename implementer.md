# implementer.md — Agente Implementador
Lee MEMORY.md y constitution.md antes de editar. Cambios mínimos, type hints, tests en el mismo cambio.
Acceso a BD solo en `app/services/dataset_service.py` (CALL parametrizado %s, wait_for timeout, drenar nextset, rollback en finally).
Nunca secretos reales; placeholders y variables de entorno. Ejecuta `pytest -q` y reporta el resultado real; si no pudiste ejecutarlo, dilo.
