# constitution.md — Reglas No Negociables del Proyecto HTA API

> Ningún agente, desarrollador ni commit puede violar estas reglas.
> El Revisor rechaza cualquier cambio que las infrinja.

---

## Seguridad

1. **Sin secretos reales en archivos del repositorio.** Ninguna clave, contraseña, token, hash real, certificado ni cadena de conexión aparece en código, commits, logs ni comentarios. Solo placeholders (`<VALOR>`, env vars).
2. **TLS MySQL obligatorio en producción.** `DB_SSL_CA` debe apuntar a un certificado CA válido. `verify_mode=CERT_REQUIRED` y `check_hostname=True` siempre activos. Nunca `ssl=None` en producción ni `verify=False` en ningún cliente.
3. **Sin SQL Injection.** Todo parámetro al SP se pasa via `cursor.execute(sql, params)` con placeholders `%s`. Nunca concatenación de strings en SQL.
4. **Sin logs de dataset ni de claves.** `structlog` configurado para no serializar cuerpos de respuesta, headers `X-API-Key` ni datos de pacientes. Solo metadatos: `request_id`, `key_id`, `idsociedad`, `row_count`, tiempos.
5. **Sin exposición directa de puerto.** En producción, solo Cloudflare Tunnel. Sin `host: 0.0.0.0` expuesto en firewall público.
6. **Privilegios mínimos en MySQL.** El usuario `api_hta` solo tiene `EXECUTE` sobre el SP. Sin `SELECT`, `INSERT`, `UPDATE`, `DELETE` directos en tablas.
7. **Sin cache de datos clínicos en Cloudflare.** `Cache-Control: no-store, no-cache` en todas las respuestas de datos.

---

## Integridad del SP

8. **Sin modificar ni recrear el SP.** `SP_Procesos_dataset_pacientes_HTA` y las tablas subyacentes son de solo lectura desde el punto de vista de esta API. Ningún agente propone DDL sobre ellas sin petición explícita del propietario de la BD.
9. **Sin escrituras visibles.** El SP no tiene escrituras visibles en las capturas. Si se descubre alguna, reportar antes de continuar.

---

## Calidad de código

10. **Tests antes de merge.** Todo cambio funcional incluye test unitario correspondiente. `pytest tests/ -v` debe pasar en verde.
11. **Tipos explícitos.** Todo el código Python usa type hints en funciones públicas. El DTO `DatasetRecord` no admite campos sin tipo.
12. **Sin `# type: ignore` sin justificación.** Documentar el motivo en el mismo comentario.
13. **Sin `asyncio.sleep(0)` como workaround de concurrencia.** Resolver el problema real.

---

## Operaciones

14. **Un worker por defecto.** Documentar explícitamente antes de escalar a múltiples workers; actualizar caché y rate limiter a Redis.
15. **Timeout en toda llamada al SP.** `asyncio.wait_for(..., timeout=settings.db_query_timeout)` siempre presente. Sin CALL sin timeout.
16. **Pool acotado.** `pool_max ≤ 20` por defecto. No aumentar sin prueba de carga real.
17. **Rollback preventivo.** `conn.rollback()` en bloque `finally` al devolver conexión al pool, aunque el SP sea de solo lectura.
