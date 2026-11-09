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