import asyncio
from app.services.cache import HTACache
from tests.conftest import BODY


def test_sin_clave_401(setup):
    c, _, _ = setup
    assert c.post("/api/v1/dataset/hta", json=BODY).status_code == 401


def test_clave_invalida_401(setup):
    c, _, _ = setup
    assert c.post("/api/v1/dataset/hta", json=BODY, headers={"X-API-Key": "hta_cli01_x"}).status_code == 401


def test_sociedad_no_autorizada_403(setup):
    c, raw, _ = setup
    r = c.post("/api/v1/dataset/hta", json={**BODY, "idsociedad": 9}, headers={"X-API-Key": raw})
    assert r.status_code == 403


def test_validacion_fechas_422(setup):
    c, raw, _ = setup
    r = c.post("/api/v1/dataset/hta", json={**BODY, "fecha_valida_dias": "2020-01-01"}, headers={"X-API-Key": raw})
    assert r.status_code == 422


def test_ok_cache_y_parametros(setup):
    c, raw, pool = setup
    h = {"X-API-Key": raw}
    r1 = c.post("/api/v1/dataset/hta", json=BODY, headers=h)
    r2 = c.post("/api/v1/dataset/hta?fmt=csv", json=BODY, headers=h)
    assert r1.status_code == 200 and len(r1.json()) == 1 and len(r1.json()[0]) == 17
    assert r1.headers["X-Cache"] == "MISS" and r2.headers["X-Cache"] == "HIT"
    assert "no-store" in r1.headers["Cache-Control"]
    assert r2.text.startswith("id_reg,sexo")
    assert len(pool.calls) == 1
    sql, params = pool.calls[0]
    assert "%s" in sql and str(params[0]) == "2019-01-01" and params[3] == 3


def test_rate_limit_429(setup):
    c, raw, _ = setup
    h = {"X-API-Key": raw}
    codes = [c.post("/api/v1/dataset/hta", json=BODY, headers=h).status_code for _ in range(4)]
    assert codes[-1] == 429


async def test_single_flight():
    cache = HTACache(60)
    n = 0
    async def fetch():
        nonlocal n
        n += 1
        await asyncio.sleep(0.05)
        return [1]
    await asyncio.gather(*[cache.get_or_fetch("k", fetch) for _ in range(50)])
    assert n == 1
