# MEMORY.md — Memoria Compartida del Proyecto HTA API

> Actualizar esta sección al completar cambios significativos.
> Los agentes deben leer este archivo antes de iniciar cualquier tarea.

---

## Estado actual del proyecto

| Item | Estado |
|------|--------|
| Código base inicial | ✅ Generado |
| Tests unitarios | ✅ Generados (sin conexión real) |
| Integración real MySQL | ⏳ Pendiente (carga y conexión real no verificadas) |
| Prueba de carga 100 usuarios | ⏳ Pendiente |
| Cloudflare Tunnel configurado | ⏳ Pendiente (requiere cuenta y token) |
| Claves de API de producción creadas | ⏳ Pendiente (usar manage_keys.py) |

---

## Decisiones tomadas

1. **Driver async:** `aiomysql 0.2` — no bloquea event loop; se usa `cursor.execute("CALL ...")`
2. **1 worker uvicorn** — suficiente con caché TTL; Redis documentado como upgrade path
3. **Caché in-memory** con `asyncio.Lock` por clave — single-flight sin Redis
4. **argon2id** para hash de API keys — sin IdP externo
5. **Cloudflare Tunnel** como exposición default — sin puertos abiertos
6. **SP no modificado** — se llama tal como existe; no recrear ni alterar
7. **Python 3.12+** — target mínimo; Ubuntu 24.04 LTS asumido como prod
8. **`SQL SECURITY DEFINER`** en SP — usuario API solo necesita EXECUTE

---

## Conocimiento del dominio

- El SP `SP_Procesos_dataset_pacientes_HTA` devuelve datos para predicción de abandono terapéutico en HTA (hipertensión arterial).
- Sociedad (`idsociedad`) es el discriminador de acceso — cada cliente solo puede ver sus pacientes.
- `fecha_valida_dias` es la fecha de corte para calcular `abandono_seguimiento`; debe ser ≥ `fecha_fin`.
- La función `extract_number()` está en la BD y parsea texto libre de notas clínicas. Puede devolver NULL.
- El campo `edad_calculada` usa `CURDATE()` en el SP — cambia con el tiempo para el mismo paciente.
- Medición baseline Navicat: 2192 filas, 1,205 s (individual, sin carga).
- Dataset seudonimizado pero sigue siendo sensible (datos de salud).

---

## Upgrade path documentado (no implementado)

- **Múltiples workers uvicorn:** reemplazar caché in-memory por Redis (redis-py async).
- **Rate limiter distribuido:** reemplazar sliding window in-memory por Redis ZADD/ZREMRANGEBYSCORE.
- **Autenticación IdP:** reemplazar `get_current_key()` por OAuth2/JWT manteniendo la interfaz de `KeyData`.
- **MySQL 8.0:** driver y código compatibles; solo actualizar `DB_HOST` y usuario.

---

## Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `app/config.py` | Todas las variables configurables |
| `app/auth/api_keys.py` | Lógica de claves — modificar aquí para auth alternativa |
| `app/services/cache.py` | Caché — reemplazar por Redis aquí |
| `app/services/dataset_service.py` | CALL SP — punto único de acceso a BD |
| `config/api_keys.json` | Almacén de claves (montar como secreto en prod) |
| `scripts/manage_keys.py` | CLI para gestión de claves |

---

## Variables de entorno críticas

```
DB_HOST           Host MySQL (red privada/VPN)
DB_PASSWORD       Contraseña MySQL (secreto)
DB_SSL_CA         Path al certificado CA de MySQL (vacío = sin TLS, solo dev)
API_KEYS_FILE     Path al JSON de claves (default: config/api_keys.json)
CACHE_TTL_SECONDS TTL de caché en segundos (default: 600)
DOCS_ENABLED      true/false — habilitar /docs (default: false en prod)
```
