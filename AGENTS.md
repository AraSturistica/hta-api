# AGENTS.md — Registro de Agentes del Proyecto HTA API

> Este archivo describe los roles, archivos de instrucciones y puntos de entrada de cada
> agente disponible para Codex u otro sistema de agentes. No afirma capacidades instaladas;
> documenta intenciones y responsabilidades.

---

## Agentes registrados

| Agente | Archivo de instrucciones | Responsabilidad principal |
|--------|--------------------------|---------------------------|
| Coordinador | `coordinator.md` | Descompone tareas, asigna agentes, valida entregables |
| Planificador | `planner.md` | Diseña flujos, secuencias de cambio, dependencias |
| Implementador | `implementer.md` | Escribe código Python, tests, Docker, scripts |
| Revisor | `reviewer.md` | Revisa seguridad, calidad, cobertura, arquitectura |

---

## Punto de entrada por tarea

| Tarea | Agente inicial |
|-------|----------------|
| Nueva funcionalidad | Planificador → Implementador → Revisor |
| Corrección de bug | Implementador → Revisor |
| Revisión de seguridad | Revisor |
| Cambio de SP o parámetros | Coordinador → Planificador → Implementador |
| Rotación de API keys | Implementador (script manage_keys.py) |
| Actualización de dependencias | Revisor → Implementador |

---

## Memoria compartida

- Leer `MEMORY.md` antes de comenzar cualquier tarea.
- Escribir en `MEMORY.md` al completar cambios arquitectónicos o decisiones.
- Las reglas no negociables están en `constitution.md`.

---

## Convenciones de comunicación

- Los agentes NO inventan comandos de instalación de herramientas no listadas en `requirements.txt`.
- Los agentes NO generan secretos reales, contraseñas, tokens ni claves en archivos del repositorio.
- Los agentes producen código con placeholders (`<VALOR>`) para todo secreto.
- El Revisor bloquea cualquier PR que viole `constitution.md`.
