# Arquitectura Técnica — API Python para Dataset HTA

> **Proyecto:** APi para HTA — Predicción de abandono de seguimiento en pacientes hipertensos  
> **Destinatario:** Abelardo Roman  
> **Estado:** Diseño completo + código funcional entregado  
> **Supuesto de producción:** Ubuntu 24.04 LTS (el coordinador indicó "Ubuntu 26"; se asume 24.04 LTS como base estable disponible; ajustar si el equipo real corre 26.04 cuando esté disponible)  
> **Integración real y carga concurrente:** pendientes de prueba en entorno real con conexión MySQL y VPN activa

---

## 1. Stack técnico justificado

| Capa | Componente | Versión mín. | Justificación |
|------|-----------|-------------|---------------|
| Lenguaje | Python | 3.12 | Requerido; disponible en Ubuntu 24.04 LTS |
| Framework API | FastAPI | 0.115 | Async nativo, OpenAPI automático, Pydantic v2 integrado, tipado estricto |
| Servidor ASGI | Uvicorn + httptools | 0.32 | ASGI de alta performance; 1 worker es suficiente con I/O async y caché |
| Driver MySQL | aiomysql | 0.2 | Driver async para MySQL 5.7, no bloquea event loop; envuelve PyMySQL |
| ORM/Pool | aiomysql.Pool | — | Pool acotado (default max=20) con `wait_created`; sin ORM (SP directo) |
| Validación / DTO | Pydantic v2 | 2.10 | Validación estricta de entrada y salida, coerción de tipos, tipado 17 columnas |
| Configuración | pydantic-settings | 2.7 | Carga `.env` → `Settings`; secretos por variables de entorno/montaje |
| Autenticación | API Keys + argon2-cffi | 23.1 | Argon2id para hash de claves; sin IdP externo; scope por sociedad |
| Caché | In-memory TTL + asyncio.Lock | — | Single-flight por clave; sin Redis (un worker; documentado para escala) |
| Rate limiting | Sliding window in-memory | — | Por `key_id`; sin Redis (un worker; documentado para escala) |
| Logging | structlog | 24.4 | JSON estructurado; sin dataset ni claves en logs |
| Testing | pytest + pytest-asyncio | 8.3 / 0.24 | Mocks async de pool y SP; sin conexión real requerida |
| Cliente | httpx + pandas | 0.28 / 2.2 | Cliente async/sync; conversión a DataFrame tipado |
| Exposición Internet | Cloudflare Tunnel (cloudflared) | — | Default seguro; sin puerto abierto; TLS extremo a extremo |
| TLS MySQL | ssl (stdlib) + CA cert | — | Verificación CA + hostname obligatoria en producción |
| Contenedor | Docker + Docker Compose | 24 / 2.29 | Reproducible en Windows (dev) y Ubuntu (prod) |
| **Frontend** | **— No aplica —** | — | No solicitado; OpenAPI docs disponibles vía env var |

---

## 2. Árbol de archivos

```
hta-api/
├── arquitectura.md              ← Este documento
├── AGENTS.md                    ← Registro de agentes y puntos de entrada
├── MEMORY.md                    ← Memoria compartida entre sesiones de Codex
├── constitution.md              ← Reglas no negociables del proyecto
├── coordinator.md               ← Instrucciones del agente coordinador
├── implementer.md               ← Instrucciones del agente implementador
├── planner.md                   ← Instrucciones del agente planificador
├── reviewer.md                  ← Instrucciones del agente revisor
├── Dockerfile
├── docker-compose.yml
├── .env.example                 ← Plantilla de variables; nunca secretos reales
├── requirements.txt             ← Dependencias versionadas
├── pytest.ini
├── config/
│   └── api_keys.json.example    ← Formato de almacén de claves (placeholder)
├── app/
│   ├── __init__.py
│   ├── main.py                  ← App factory; lifespan (pool, caché, semáforo)
│   ├── config.py                ← Settings (pydantic-settings)
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── api_keys.py          ← Carga, hash argon2id, verificación, scopes
│   │   └── dependencies.py      ← FastAPI Depends: get_current_key
│   ├── db/
│   │   ├── __init__.py
│   │   └── pool.py              ← create_pool con TLS; Depends: get_pool
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py           ← DatasetRequest (4 parámetros validados)
│   │   └── response.py          ← DatasetRecord DTO (17 columnas tipadas)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cache.py             ← HTACache: TTL + single-flight por asyncio.Lock
│   │   ├── rate_limiter.py      ← RateLimiter: sliding window per key
│   │   └── dataset_service.py   ← call_hta_sp: CALL SP, drain nextset, timeout
│   └── routers/
│       ├── __init__.py
│       └── dataset.py           ← POST /api/v1/dataset/hta (JSON o CSV)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              ← Fixtures: app de prueba, mock pool, mock SP
│   ├── test_auth.py             ← Hash, verify, scope, header inválido
│   ├── test_dataset.py          ← Endpoint: 200, 401, 403, 429, timeout
│   └── test_cache.py            ← TTL, single-flight, invalidación
├── cliente/
│   └── hta_client.py            ← HTAClient: requests/httpx → pandas.DataFrame
└── scripts/
    └── manage_keys.py           ← CLI: create / list / revoke / rotate claves
```

---

## 3. Modelo de entidades

### 3.1 Esquema lógico inferido (DDL original no disponible)

> **Advertencia:** Las relaciones y tipos siguientes se infieren del SP visible. No reemplaza el DDL real. No ejecutar DDL propio.

```
pacientes (p)
  p.id            INT  PK
  p.sexo          VARCHAR (valores 'HOMBRE' / otro)
  p.FechaNac      DATE
  p.idsociedad    INT  FK → sociedad

historiaclinica_notas (hn / nl)
  hn.idnota       INT  PK
  hn.idpaciente   INT  FK → pacientes.id
  hn.idsociedad   INT
  hn.fecalta      DATETIME
  hn.imc          VARCHAR  (texto libre; parseado por extract_number())
  hn.tas          VARCHAR  (texto libre; parseado por extract_number())
  hn.tad          VARCHAR  (texto libre; parseado por extract_number())

historiaclinica (h2)
  h2.idpaciente   INT  FK → pacientes.id
  h2.fecalta      DATETIME
  h2.ejercicio    NUMERIC (nullable)
  h2.alcohol      NUMERIC (nullable)
  h2.diabetesii   NUMERIC (nullable; alias diabetesii en SP)
  h2.dislipidemia NUMERIC (nullable)
  h2.cancer       NUMERIC (nullable)
  h2.hipersist    NUMERIC (nullable)
  h2.controlhip, h2.complicahip, h2.otrasenfermedades, h2.historiacardio,
  h2.diagnostico, h2.diagnostico2, h2.tratamiento, h2.numcesareas,
  h2.tipoplanificacion, h2.dislipicontrol, h2.dislipianos, h2.tabaco,
  h2.activoalcohol  (columnas visibles en SELECT h2.*; tipos desconocidos)

Función MySQL: extract_number(texto VARCHAR) → DECIMAL  (definida en BD; no recrear)

Relaciones visibles:
  hn/nl.idpaciente → p.id  (INNER JOIN en subquery agg; LEFT JOIN para última nota)
  h2.idpaciente → p.id  (LEFT JOIN seleccionando MAX(fecalta) por paciente)
  hn.idsociedad = p_idsociedad  (filtro de sociedad)
  p.idsociedad = p_idsociedad   (filtro de sociedad en tabla base)
```

### 3.2 DTO `DatasetRecord` — 17 columnas tipadas

| # | Nombre columna SP | Tipo Python | Nullable | Notas |
|---|-------------------|-------------|----------|-------|
| 1 | `id_reg` | `int` | No | p.id; PK lógico |
| 2 | `sexo` | `int` | No | IF(TRIM='HOMBRE',1,0); siempre 0 ó 1 |
| 3 | `ejercicio` | `float` | No* | IFNULL(h.ejercicio, 0); 0 cuando sin historia |
| 4 | `alcohol` | `float` | No* | IFNULL(h.alcohol, 0); 0 cuando sin historia |
| 5 | `edad_calculada` | `int` | No | IFNULL(TIMESTAMPDIFF…, 0) |
| 6 | `numero_total_consultas` | `int` | No | COUNT(*) ≥ 1 (INNER JOIN) |
| 7 | `anio_primera_consulta` | `int` | No | YEAR(MIN(hn.fecalta)) |
| 8 | `fecha_primera_consulta` | `date \| None` | Sí† | DATE_FORMAT '%Y-%m-%d'; string → date |
| 9 | `fecha_ultima_consulta` | `date \| None` | Sí† | DATE_FORMAT '%Y-%m-%d'; string → date |
| 10 | `dias_desde_ultima_consulta` | `int \| None` | Sí | DATEDIFF puede ser NULL si fecha es NULL |
| 11 | `promedio_dias_entre_citas` | `float \| None` | Sí | 0 si COUNT=1; ROUND(…,2) si >1 |
| 12 | `citas_por_ano` | `float \| None` | Sí | ROUND(COUNT/GREATEST(DISTINCT YEARS,1),2) |
| 13 | `abandono_seguimiento` | `int` | No | CASE DATEDIFF≥365→1 ELSE 0 |
| 14 | `imc_ultimo` | `float \| None` | Sí | extract_number(nl.imc); NULL si sin nota |
| 15 | `tas_ultimo` | `float \| None` | Sí | extract_number(nl.tas); NULL si sin nota |
| 16 | `tad_ultimo` | `float \| None` | Sí | extract_number(nl.tad); NULL si sin nota |
| 17 | `num_comorbilidades` | `int` | No | COALESCE(diabetesii,0)+dislip+cancer+hiper |

> † Teóricamente no nulo con INNER JOIN, pero Pydantic acepta None defensivamente.  
> * Los campos de historiaclinica son 0 por IFNULL cuando el LEFT JOIN no encuentra registro.

---

## 4. Flujo de solicitud (paso a paso)

```
Cliente Python
    │
    │  POST /api/v1/dataset/hta
    │  Header: X-API-Key: hta_<32hex>
    │  Body: {fecha_inicio, fecha_fin, fecha_valida_dias, idsociedad}
    │
    ▼
[1] CLOUDFLARE TUNNEL
    Termina TLS externo → reenvía a localhost:8000 en servidor Ubuntu
    (Sin exposición de puerto directo; sin cache de Cloudflare para datos clínicos)
    │
    ▼
[2] UVICORN (ASGI) → FastAPI
    Parsea request; adjunta X-Request-ID único
    │
    ▼
[3] MIDDLEWARE LOGGING
    Log de entrada: método, ruta, IP, request_id (SIN body, SIN clave)
    │
    ▼
[4] AUTENTICACIÓN — dependencies.get_current_key()
    - Extrae header X-API-Key
    - Busca en KeyStore (cargado en memoria al inicio; recarga bajo demanda)
    - Verifica argon2id.verify(stored_hash, provided_key)
    - Si falla → HTTP 401 (mensaje genérico, sin indicar si key existe)
    │
    ▼
[5] VALIDACIÓN DE ENTRADA — Pydantic DatasetRequest
    - fecha_inicio, fecha_fin: date válida; inicio ≤ fin
    - fecha_valida_dias: date válida; ≥ fecha_fin (semántica SP)
    - idsociedad: int > 0
    - Si falla → HTTP 422 con detalle de campo
    │
    ▼
[6] AUTORIZACIÓN DE SOCIEDAD
    - key_data.scopes contiene idsociedad solicitado
    - Si falla → HTTP 403 "clave no autorizada para esta sociedad"
    │
    ▼
[7] RATE LIMITING — RateLimiter.check(key_id)
    - Ventana deslizante en memoria por key_id
    - Límite configurable por clave (default 100 req/hora)
    - Si excede → HTTP 429 con Retry-After header
    │
    ▼
[8] CACHÉ — HTACache.get_or_fetch(cache_key, fetch_coro)
    - cache_key = f"{idsociedad}|{fecha_inicio}|{fecha_fin}|{fecha_valida}"
    - Si HIT y no expirado (TTL configurable, default 10 min) → retorna cached
    - Si MISS: asyncio.Lock por cache_key → single-flight
      (Segundo caller con mismos params espera al primero; lee de caché al despertar)
    │
    ▼  (solo si MISS)
[9] SEMÁFORO DE CONCURRENCIA
    - asyncio.Semaphore(max_concurrent_sp_calls, default=25)
    - Limita SP simultáneos sin abrir >pool_max conexiones MySQL
    │
    ▼
[10] POOL aiomysql — CALL SP
    - pool.acquire() → Connection (pool_max=20 por defecto)
    - SET SESSION max_execution_time = <ms>  (MySQL 5.7: sólo para SELECT; documentado)
    - asyncio.wait_for(CALL SP_Procesos_dataset_pacientes_HTA(%s,%s,%s,%s), timeout=60s)
    - cur.fetchall() → list[dict]
    - Drain nextset() hasta agotamiento (OK packet final de CALL)
    - conn.rollback() preventivo al liberar
    │
    ▼
[11] MAPPING → DTO
    - DatasetRecord.model_validate(row) por cada fila
    - Coerción: strings fecha → date; None → Optional fields
    - Fila inválida → ValidationError → HTTP 500 con log detallado
    │
    ▼
[12] ESCRITURA EN CACHÉ
    - Almacena list[DatasetRecord] serializado
    - TTL = settings.cache_ttl_seconds (default 600 s)
    │
    ▼
[13] RESPUESTA
    - format=json (default): JSONResponse list[DatasetRecord]
    - format=csv: StreamingResponse text/csv con DictWriter
    - Headers: X-Request-ID, X-Cache (HIT/MISS), X-Row-Count
    │
    ▼
Cliente Python → pandas.DataFrame con dtypes tipados
```

---

## 5. Decisiones arquitectónicas

### DA-1: Un solo worker Uvicorn + aiomysql async
**Decisión:** Uvicorn con un proceso, event loop async, driver aiomysql.  
**Justificación:** 100 usuarios concurrentes con SP de ~1,2 s y caché de 10 min resultan en ≤ 10 SP simultáneos reales (el resto lee caché). Un worker async maneja esto sin GIL ni comunicación entre procesos. Redis y múltiples workers se documentan como upgrade path, no como requerimiento inicial.  
**Trade-off:** Si el SP tarda más o la caché se invalida masivamente, puede saturarse. Mitigación: semáforo + pool acotado + timeout.

### DA-2: API Keys con argon2id + scopes por sociedad
**Decisión:** Claves en formato `hta_<32hex>`, hash argon2id almacenado en JSON montado como secreto. Sin IdP externo.  
**Justificación:** No se indicó proveedor de identidad existente; API Keys son el mecanismo más simple, seguro y sin dependencias externas para clientes Python. argon2id es el estándar actual de hashing de contraseñas/tokens. Los scopes garantizan aislamiento entre sociedades con una sola API.  
**Trade-off:** Rotación manual de claves vía script. Si se integra un IdP en el futuro, el mecanismo de Depends es fácilmente reemplazable.

### DA-3: Caché in-memory con single-flight (sin Redis)
**Decisión:** Dict Python + asyncio.Lock por clave de caché. TTL configurable.  
**Justificación:** Con 1 worker, la caché in-process es consistente y sin latencia de red. El patrón single-flight (segundo caller espera al primero con mismos params) evita thundering herd contra MySQL. 100 usuarios pidiendo el mismo dataset ejecutan 1 SP, no 100.  
**Trade-off:** La caché no persiste entre reinicios ni se comparte entre workers. Documentado en MEMORY.md.

### DA-4: Cloudflare Tunnel como exposición a Internet (default)
**Decisión:** `cloudflared tunnel` conecta el proceso local al edge de Cloudflare sin abrir puertos.  
**Justificación:** Elimina exposición directa de IP, gestión de certificados TLS externos y reglas de firewall. La verificación TLS MySQL CA+hostname se realiza internamente desde la API hacia la BD. Cloudflare no cachea respuestas (configurado con `Cache-Control: no-store`).  
**Trade-off:** Dependencia del servicio Cloudflare; si el túnel cae, la API no es accesible. Mitigación: supervisión con `restart: unless-stopped` en docker-compose.

### DA-5: Call directo a SP — sin capa ORM
**Decisión:** `CALL SP_Procesos_dataset_pacientes_HTA(...)` vía `cursor.execute()`. Sin SQLAlchemy Core ni ORM.  
**Justificación:** El SP existe y no debe modificarse. SQLAlchemy no aporta ventaja para un único CALL parametrizado. aiomysql ofrece el pool acotado que necesitamos. Eliminar ORM reduce superficie de error y dependencias.  
**Trade-off:** Si se agrega lógica de escritura futura, se requerirá más código manual. Para el scope actual es la opción correcta.

---

## 6. Riesgos y mitigaciones

### R-1: Seguridad + compatibilidad MySQL 5.7

| Aspecto | Riesgo | Mitigación |
|---------|--------|------------|
| TLS MySQL | Comunicación en texto claro en red privada/VPN | `ssl_ca` obligatorio en producción; `verify_mode=CERT_REQUIRED`; `check_hostname=True`; entorno dev sin SSL explícito |
| SQL Injection | Parámetros del SP enviados como literales | `cursor.execute(sql, params)` con placeholder `%s`; PyMySQL escapa; NO concatenación de strings |
| Exposición de claves | Clave en header HTTP visible en logs | `X-API-Key` nunca logueado; solo se loguea `key_id`; `structlog` configurado para no serializar headers sensibles |
| MySQL 5.7 EOL | Sin soporte de seguridad desde Oct 2023 | Documentar riesgo al equipo; plan de migración a MySQL 8.0 recomendado; API compatible con 8.0 sin cambios |
| Privilegios DB | Usuario de API con EXECUTE + SELECT innecesarios | Crear usuario con `GRANT EXECUTE ON PROCEDURE clinicas.SP_Procesos_dataset_pacientes_HTA TO 'api_user'@'%'`; SP usa `SQL SECURITY DEFINER` |
| Secretos en archivos | `.env` o `api_keys.json` en imagen Docker | `.dockerignore` excluye ambos; montaje como volumen secreto en producción |

### R-2: Carga y concurrencia

| Aspecto | Riesgo | Mitigación |
|---------|--------|------------|
| 100 usuarios simultáneos | Medición de 1,2 s es individual; concurrencia no verificada | Pool max=20, semáforo max=25, caché TTL=600s; SP simultáneos reales ≤ 1 con mismos params |
| Saturación de pool | Requests superan pool_max esperando conexión | `pool_timeout` configurable; respuesta 503 tras timeout; logs de alerta |
| Memory leak caché | Combinaciones únicas (sociedad×fecha) llenan RAM | `maxsize` configurable; LRU-like con TTL; caché ocupa ~2KB/fila×2192 filas ≈ 4 MB por entrada |
| SP lento en concurrencia | MySQL 5.7 sin query cache en concurrencia alta | asyncio.wait_for timeout=60s; índices en `fecalta` e `idsociedad` recomendados (no modificar sin petición) |
| Multi-worker futuro | Caché y rate limiter in-memory no compartidos | Migración a Redis documentada en MEMORY.md como upgrade path claro |

### R-3: Calidad de datos temporales / uso en ML

| Aspecto | Riesgo | Mitigación |
|---------|--------|------------|
| `fecha_valida_dias` semántica | Corte arbitrario afecta `abandono_seguimiento`; mal uso invalida dataset | Validación: `fecha_valida_dias ≥ fecha_fin`; documentado en OpenAPI; cliente valida antes de enviar |
| `extract_number()` NULL | Función retorna NULL para texto no parseable; columnas IMC/TAS/TAD opcionales | DTO con `Optional[float]`; cliente advierte % de NULLs antes de entrenar modelo |
| Edad calculada dinámica | `CURDATE()` en SP → edad cambia cada día para mismo paciente | El campo `edad_calculada` depende de cuándo se ejecuta el SP; documentar en metadata de respuesta |
| Seudonimización insuficiente | Dataset sigue siendo sensible; `id_reg` podría reidentificar | No cachear en Cloudflare (`Cache-Control: no-store`); HTTPS extremo a extremo; logs sin dataset |

---

## 7. Configuración Cloudflare Tunnel

> **Integración real pendiente:** requiere cuenta Cloudflare y `cloudflared` instalado.

```yaml
# En docker-compose.yml (sección cloudflared)
cloudflared:
  image: cloudflare/cloudflared:latest
  restart: unless-stopped
  command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
  environment:
    - CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
```

**Pasos manuales (una vez):**
1. `cloudflared tunnel create hta-api` → genera TUNNEL_TOKEN
2. En dashboard Cloudflare: configurar ruta `https://hta.tudominio.com` → `http://localhost:8000`
3. En docker-compose: pasar `CLOUDFLARE_TUNNEL_TOKEN` como secreto de entorno (nunca en imagen)

**Por qué NO `verify=False` en cliente:**  
Cloudflare termina TLS con certificado válido; los clientes Python deben verificar normalmente. `httpx.Client(verify=True)` es el default correcto.

---

## 8. Privilegios mínimos MySQL

```sql
-- Ejecutar una vez en MySQL 5.7 como administrador
CREATE USER 'api_hta'@'%' IDENTIFIED BY '<contraseña_fuerte>';
GRANT EXECUTE ON PROCEDURE clinicas.SP_Procesos_dataset_pacientes_HTA TO 'api_hta'@'%';
-- NO GRANT SELECT, INSERT, UPDATE, DELETE en tablas directamente
-- El SP usa SQL SECURITY DEFINER con el usuario propietario (abelardo@%)
FLUSH PRIVILEGES;
```

---

## 9. Variables de entorno requeridas

Ver `.env.example` para lista completa. Las mínimas para producción:

```
DB_HOST=<host_mysql_en_red_privada>
DB_PASSWORD=<secreto_nunca_en_imagen>
DB_SSL_CA=/run/secrets/mysql-ca.pem
API_KEYS_FILE=/run/secrets/api_keys.json
```

---

## 10. Despliegue reproducible

### Desarrollo Windows (PyCharm + Codex)
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # Editar con valores locales (sin SSL para dev)
# DB_SSL_CA= (vacío = sin TLS, solo para dev local con MySQL accesible)
uvicorn --factory app.main:_factory --reload --port 8000
```

### Producción Ubuntu (Docker Compose)
```bash
# 1. Copiar secretos (nunca en repo)
cp config/api_keys.json.example config/api_keys.json  # editar con hashes reales
# 2. Configurar .env con valores reales
cp .env.example .env  # editar
# 3. Levantar
docker compose up -d
# 4. Verificar
docker compose logs -f api
curl -H "X-API-Key: hta_..." http://localhost:8000/health
```

### Tests
```bash
pytest -q
```
