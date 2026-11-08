import pytest
from contextlib import asynccontextmanager
from fastapi.testclient import TestClient
from app.auth.api_keys import KeyData, KeyStore, generate_key
from app.config import Settings
from app.main import create_app

ROW = {"id_reg": 1, "sexo": 1, "ejercicio": 0, "alcohol": 0, "edad_calculada": 60,
       "numero_total_consultas": 3, "anio_primera_consulta": 2019,
       "fecha_primera_consulta": "2019-02-01", "fecha_ultima_consulta": "2023-05-02",
       "dias_desde_ultima_consulta": 610, "promedio_dias_entre_citas": 755.5,
       "citas_por_ano": 1.5, "abandono_seguimiento": 1, "imc_ultimo": 27.3,
       "tas_ultimo": 140, "tad_ultimo": 90, "num_comorbilidades": 2}


class FakeCursor:
    def __init__(self, calls): self.calls = calls
    async def __aenter__(self): return self
    async def __aexit__(self, *a): pass
    async def execute(self, sql, params): self.calls.append((sql, params))
    async def fetchall(self): return [ROW]
    async def nextset(self): return None


class FakeConn:
    closed = False
    def __init__(self, calls): self.calls = calls
    def cursor(self, *a): return FakeCursor(self.calls)
    async def rollback(self): pass
    def close(self): self.closed = True


class FakePool:
    def __init__(self): self.calls = []
    @asynccontextmanager
    async def acquire(self): yield FakeConn(self.calls)


@pytest.fixture
def setup():
    raw, h = generate_key("cli01")
    ks = KeyStore([KeyData("cli01", h, [3], rate_per_hour=3)])
    pool = FakePool()
    app = create_app(Settings(_env_file=None), pool=pool, keystore=ks)
    with TestClient(app) as c:
        yield c, raw, pool

BODY = {"fecha_inicio": "2019-01-01", "fecha_fin": "2024-12-31", "fecha_valida_dias": "2025-01-01", "idsociedad": 3}
