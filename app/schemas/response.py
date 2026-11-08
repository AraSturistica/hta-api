from datetime import date
from pydantic import BaseModel


class DatasetRecord(BaseModel):
    """17 columnas del SP. Nulabilidad defensiva donde el DDL real es desconocido."""
    id_reg: int
    sexo: int
    ejercicio: float | None = None
    alcohol: float | None = None
    edad_calculada: int | None = None
    numero_total_consultas: int | None = None
    ano_primera_consulta: int | None = None
    fecha_primera_consulta: date | None = None
    fecha_ultima_consulta: date | None = None
    dias_desde_ultima_consulta: int | None = None
    promedio_dias_entre_citas: float | None = None
    citas_por_ano: float | None = None
    abandono_seguimiento: int | None = None
    imc_ultimo: float | None = None
    tas_ultimo: float | None = None
    tad_ultimo: float | None = None
    num_comorbilidades: int | None = None

COLUMNS = list(DatasetRecord.model_fields)
