# Ajuste: MySQL sin CA en producción mediante excepción explícita (`DB_ALLOW_NO_CA`)

**Proyecto:** APi para HTA · **Alcance:** solo la configuración TLS del pool MySQL. No toca HTTPS/Cloudflare, autenticación, límites, caché, esquemas ni cliente.

## 1. Qué cambia

| Situación | Antes | Ahora |
|---|---|---|
| `ENVIRONMENT=production`, sin CA, `DB_ALLOW_NO_CA=false` (por defecto) | RuntimeError | RuntimeError (sin cambio) |
| `ENVIRONMENT=production`, sin CA, `DB_ALLOW_NO_CA=true` | RuntimeError | `ssl=None` + WARNING en logs |
| Con CA (cualquier entorno y valor de opt-in) | CERT_REQUIRED + hostname | CERT_REQUIRED + hostname (sin cambio) |
| `ENVIRONMENT=development`, sin CA | `ssl=None` | `ssl=None` (sin cambio, sin aviso) |

No se usa `CERT_NONE` en ningún caso. `ENVIRONMENT` sigue siendo `production`.

> ⚠️ **`ssl=None` NO garantiza cifrado.** Con esta excepción, la conexión API → MySQL puede viajar en texto claro (credenciales de BD y datos clínicos seudonimizados). Solo es aceptable si ese tramo pasa **exclusivamente por red privada/VPN** y el puerto 3306 de MySQL está restringido por **firewall** a la IP del servidor Ubuntu de la API. Según el usuario, MySQL es accesible por red privada/VPN; **esto no ha sido verificado**. La recomendación sigue siendo obtener la CA (o el certificado del servidor MySQL) y volver a `DB_ALLOW_NO_CA=false`.

## 2. Archivos modificados (contenido completo)

Dos archivos de código de la API y un archivo de pruebas **nuevo**.

### 2.1 `app/config.py` — única diferencia: línea `db_allow_no_ca`

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "api_hta"
    db_password: str = ""
    db_name: str = "clinicas"
    db_ssl_ca: str = ""
    db_allow_no_ca: bool = False  # Opt-in explícito para omitir CA en producción
    db_pool_max: int = 10
    db_connect_timeout: int = 10
    db_query_timeout: float = 60.0
    max_concurrent_sp: int = 8
    cache_ttl_seconds: int = 600
    cache_max_entries: int = 200
    api_keys_file: str = "config/api_keys.json"
    docs_enabled: bool = False
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 2.2 `app/db/pool.py` — `build_ssl` reescrita; `create_pool` sin cambios

```python
import logging
import ssl
import aiomysql
from app.config import Settings

logger = logging.getLogger(__name__)


def build_ssl(settings: Settings) -> ssl.SSLContext | None:
    """Construye el contexto SSL para la conexión MySQL.

    Reglas de seguridad:
    - CA configurada → CERT_REQUIRED + check_hostname siempre, independiente de DB_ALLOW_NO_CA.
    - Producción, sin CA, DB_ALLOW_NO_CA=false (default) → RuntimeError; CA obligatoria.
    - Producción, sin CA, DB_ALLOW_NO_CA=true → ssl=None + advertencia; solo usar si la
      conexión transcurre exclusivamente por red privada/VPN. No garantiza cifrado TLS.
    - Desarrollo, sin CA → ssl=None (sin advertencia; comportamiento existente).
    - Nunca se desactiva la verificación de certificado cuando hay contexto TLS.
    """
    if settings.db_ssl_ca:
        # CA presente: validación completa siempre, aunque DB_ALLOW_NO_CA sea true
        ctx = ssl.create_default_context(cafile=settings.db_ssl_ca)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx

    # Sin CA
    if settings.environment == "production":
        if not settings.db_allow_no_ca:
            raise RuntimeError(
                "DB_SSL_CA obligatorio en producción. "
                "Para omitir explícitamente fije DB_ALLOW_NO_CA=true solo si la conexión "
                "transcurre por red privada/VPN y acepta que TLS no queda verificado."
            )
        # Opt-in explícito autorizado
        logger.warning(
            "ADVERTENCIA DE SEGURIDAD: DB_ALLOW_NO_CA=true activo en producción. "
            "ssl=None: no se garantiza cifrado TLS en la conexión MySQL. "
            "Requerido: conexión exclusivamente por red privada o VPN con firewall."
        )
        return None

    # Desarrollo sin CA: ssl=None (sin advertencia)
    return None


async def create_pool(settings: Settings) -> aiomysql.Pool:
    return await aiomysql.create_pool(
        host=settings.db_host, port=settings.db_port, user=settings.db_user,
        password=settings.db_password, db=settings.db_name, minsize=1,
        maxsize=settings.db_pool_max, connect_timeout=settings.db_connect_timeout,
        ssl=build_ssl(settings), autocommit=False, pool_recycle=1800, charset="utf8mb4",
    )
```

### 2.3 `tests/test_ssl_no_ca.py` — archivo nuevo (no reemplaza ninguno)

```python
"""
Pruebas unitarias para build_ssl — excepción DB_ALLOW_NO_CA.

Alcance: solo lógica de build_ssl; sin conexión a MySQL ni a ningún servicio externo.
Para ejecutar: pytest tests/test_ssl_no_ca.py -v
"""
import inspect
import logging
import ssl

import pytest

import app.db.pool as poolmod
from app.config import Settings
from app.db.pool import build_ssl


# ---------------------------------------------------------------------------
# Helpers para construir Settings sin cargar .env
# ---------------------------------------------------------------------------

def _settings(**kwargs) -> Settings:
    """Crea Settings sin archivo .env; aplica sólo los kwargs dados."""
    return Settings(_env_file=None, **kwargs)


def _prod_no_ca(**kwargs) -> Settings:
    return _settings(environment="production", db_ssl_ca="", **kwargs)


def _prod_with_ca(ca_path: str, **kwargs) -> Settings:
    return _settings(environment="production", db_ssl_ca=ca_path, **kwargs)


# ---------------------------------------------------------------------------
# Test 1: Producción, sin CA, opt-in=False (default) → RuntimeError
# ---------------------------------------------------------------------------

def test_produccion_sin_ca_sin_optin_rechaza():
    """Sin DB_ALLOW_NO_CA la API no arranca en producción si no hay CA."""
    s = _prod_no_ca(db_allow_no_ca=False)
    with pytest.raises(RuntimeError, match="DB_SSL_CA obligatorio"):
        build_ssl(s)


# ---------------------------------------------------------------------------
# Test 2: Producción, sin CA, opt-in=True → ssl=None + advertencia en logs
# ---------------------------------------------------------------------------

def test_produccion_sin_ca_con_optin_devuelve_none(caplog):
    """Con DB_ALLOW_NO_CA=true la función devuelve None y emite WARNING."""
    s = _prod_no_ca(db_allow_no_ca=True)
    with caplog.at_level(logging.WARNING, logger="app.db.pool"):
        result = build_ssl(s)

    assert result is None, "Se esperaba ssl=None con opt-in"
    mensajes = " ".join(caplog.messages)
    assert "DB_ALLOW_NO_CA" in mensajes, "El warning debe mencionar DB_ALLOW_NO_CA"
    # Debe advertir sobre ausencia de TLS garantizado
    assert any(kw in mensajes for kw in ("TLS", "cifrado")), \
        "El warning debe mencionar ausencia de cifrado TLS garantizado"
    # Debe mencionar red privada o VPN
    assert any(kw in mensajes for kw in ("VPN", "privada")), \
        "El warning debe mencionar VPN o red privada"


# ---------------------------------------------------------------------------
# Test 3: Producción con CA + DB_ALLOW_NO_CA=True → CA tiene prioridad
#         Debe devolver SSLContext con CERT_REQUIRED y check_hostname
# ---------------------------------------------------------------------------

def _generar_ca_prueba(tmp_path):
    """Genera una CA autofirmada de prueba (solo para el test) con openssl."""
    import shutil
    import subprocess
    if shutil.which("openssl") is None:
        pytest.skip("openssl no disponible para generar CA de prueba")
    key = tmp_path / "ca-prueba.key"
    crt = tmp_path / "ca-prueba.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(crt), "-days", "1",
         "-subj", "/CN=CA de prueba HTA"],
        check=True, capture_output=True,
    )
    return crt


@pytest.mark.parametrize("optin", [False, True])
def test_produccion_con_ca_mantiene_cert_required_aunque_optin(tmp_path, optin):
    """Si hay CA configurada, CERT_REQUIRED + check_hostname sin importar DB_ALLOW_NO_CA."""
    ca_file = _generar_ca_prueba(tmp_path)
    s = _prod_with_ca(str(ca_file), db_allow_no_ca=optin)
    ctx = build_ssl(s)

    assert isinstance(ctx, ssl.SSLContext), "Con CA debe devolver un SSLContext real"
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    # La CA de prueba quedó cargada en el contexto
    assert any(c.get("subject") and "CA de prueba HTA" in str(c["subject"])
               for c in ctx.get_ca_certs())


# ---------------------------------------------------------------------------
# Test 4: Desarrollo sin CA → None sin advertencia (comportamiento existente)
# ---------------------------------------------------------------------------

def test_desarrollo_sin_ca_devuelve_none_sin_warning(caplog):
    """En desarrollo sin CA, build_ssl devuelve None y NO emite warnings."""
    s = _settings(environment="development", db_ssl_ca="", db_allow_no_ca=False)
    with caplog.at_level(logging.WARNING, logger="app.db.pool"):
        result = build_ssl(s)

    assert result is None
    assert caplog.records == [], \
        "No debe emitir warnings en desarrollo (comportamiento existente intacto)"


# ---------------------------------------------------------------------------
# Test 5: CERT_NONE ausente del código fuente (garantía de no regresión)
# ---------------------------------------------------------------------------

def test_nunca_cert_none_en_codigo():
    """CERT_NONE no aparece en pool.py en ningún caso."""
    src = inspect.getsource(poolmod)
    assert "CERT_NONE" not in src, \
        "pool.py no debe contener CERT_NONE en ningún code path"
```

## 3. Integración sin perder cambios locales

Su copia local (Windows / repositorio / Ubuntu) tiene cambios propios, como la corrección `ano_primera_consulta`. **No sobrescriba el proyecto con el ZIP original** (contiene el nombre antiguo `anio_primera_consulta`).

1. Antes de tocar nada, revise con su control de versiones si `app/config.py` o `app/db/pool.py` tienen cambios locales suyos. Si los tienen, **no reemplace el archivo entero**: aplique a mano solo las diferencias de abajo.
2. `app/config.py`: añada **una línea** debajo de `db_ssl_ca: str = ""`:
   `db_allow_no_ca: bool = False  # Opt-in explícito para omitir CA en producción`
3. `app/db/pool.py`: si no lo modificó localmente, reemplácelo completo por el de 2.2. Si lo modificó, sustituya solo la función `build_ssl` y añada arriba `import logging` y `logger = logging.getLogger(__name__)`; deje `create_pool` como lo tenga.
4. Copie `tests/test_ssl_no_ca.py` como archivo nuevo (requiere `openssl` en el PATH para la prueba con CA; si no está, esa prueba se omite con SKIP).
5. No modifique ningún otro archivo (esquemas, cliente, conftest, auth, router, etc.).
6. Ejecute `pytest tests/test_ssl_no_ca.py -v` y después `pytest -q`. Suba el cambio a su repositorio y tráigalo al Ubuntu como hace habitualmente.
7. En el `.env` de Ubuntu ajuste las variables del punto 4 y reinicie la API como lo hace normalmente. Al crear el pool debe aparecer la línea `ADVERTENCIA DE SEGURIDAD: DB_ALLOW_NO_CA=true activo en producción...` (salida de error / journal / logs del contenedor).

## 4. Variables de configuración (sin secretos)

```dotenv
ENVIRONMENT=production
DB_SSL_CA=
DB_ALLOW_NO_CA=true
DB_HOST=<ip_o_host_mysql_en_red_privada_vpn>
DB_PORT=3306
DB_USER=api_hta
DB_PASSWORD=<secreto_solo_en_el_servidor>
```

- `DB_ALLOW_NO_CA` acepta `true`/`false` (también `1`/`0`); por defecto `false`.
- Si en el futuro dispone de CA: `DB_SSL_CA=/ruta/ca.pem` y `DB_ALLOW_NO_CA=false`. Aunque quedara `true`, con CA presente se aplica la validación completa.
- En `DB_HOST` use la IP/nombre de la red privada o VPN, nunca una dirección pública.

## 5. Resultados de pruebas (reales, en el entorno del agente)

Ejecutado sobre el código del ZIP original con este parche aplicado (Python 3.11, pytest 8.3.4):

| Prueba | Resultado |
|---|---|
| Producción sin CA, sin opt-in → RuntimeError | PASSED |
| Producción sin CA, con opt-in → `None` + WARNING (menciona DB_ALLOW_NO_CA, TLS/cifrado, VPN/red privada) | PASSED |
| Producción con CA de prueba real (autofirmada con openssl), opt-in `false` → CERT_REQUIRED + check_hostname + CA cargada | PASSED |
| Ídem con opt-in `true` | PASSED |
| Desarrollo sin CA → `None`, sin warnings | PASSED |
| `CERT_NONE` ausente de `pool.py` | PASSED |
| Suite completa: 7 pruebas originales + 6 nuevas | 13 passed |

Comprobación adicional por variables de entorno: `DB_ALLOW_NO_CA=true ENVIRONMENT=production` → `ssl=None` y se imprime la advertencia; `DB_ALLOW_NO_CA=false` → RuntimeError.

**No probado:** conexión a la BD MySQL real, existencia/cifrado de la VPN, firewall, arranque en el Ubuntu del usuario, despliegue ni Cloudflare. No hubo acceso al servidor ni a la base; son pruebas unitarias de la lógica de `build_ssl`.
