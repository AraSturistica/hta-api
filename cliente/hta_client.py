"""Cliente HTA -> pandas.DataFrame. Clave por variable de entorno HTA_API_KEY (nunca en URL)."""
import os
import httpx
import pandas as pd

DTYPES = {"id_reg": "Int64", "sexo": "Int8", "ejercicio": "Float64", "alcohol": "Float64",
          "edad_calculada": "Int64", "numero_total_consultas": "Int64", "ano_primera_consulta": "Int64",
          "dias_desde_ultima_consulta": "Int64", "promedio_dias_entre_citas": "Float64",
          "citas_por_ano": "Float64", "abandono_seguimiento": "Int8", "imc_ultimo": "Float64",
          "tas_ultimo": "Float64", "tad_ultimo": "Float64", "num_comorbilidades": "Int64"}
DATES = ["fecha_primera_consulta", "fecha_ultima_consulta"]


class HTAError(Exception):
    pass


class HTAClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 90.0):
        key = api_key or os.environ.get("HTA_API_KEY")
        if not key:
            raise HTAError("Falta HTA_API_KEY")
        self._c = httpx.Client(base_url=base_url, headers={"X-API-Key": key},
                               timeout=httpx.Timeout(timeout, connect=10.0), verify=True)

    def dataset(self, fecha_inicio: str, fecha_fin: str, fecha_valida_dias: str, idsociedad: int) -> pd.DataFrame:
        body = {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin,
                "fecha_valida_dias": fecha_valida_dias, "idsociedad": idsociedad}
        try:
            r = self._c.post("/api/v1/dataset/hta", json=body)
        except httpx.TimeoutException as e:
            raise HTAError("Timeout de red") from e
        if r.status_code in (401, 403):
            raise HTAError(f"No autorizado ({r.status_code})")
        if r.status_code == 429:
            raise HTAError(f"Límite excedido; reintentar en {r.headers.get('Retry-After')} s")
        if r.status_code >= 400:
            raise HTAError(f"Error {r.status_code}: {r.text[:200]}")
        return to_dataframe(r.json())

    def close(self) -> None:
        self._c.close()


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in DATES:
        if col in df:
            df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
    return df.astype({k: v for k, v in DTYPES.items() if k in df})


if __name__ == "__main__":
    cli = HTAClient(
        base_url=os.environ.get("HTA_API_URL", "http://127.0.0.1:8000"),
        api_key=os.environ.get("HTA_API_KEY"),
    )
    df = cli.dataset("2019-01-01", "2024-12-31", "2025-01-01", 3)
    print(df.dtypes)
    print(df.head())
    cli.close()
