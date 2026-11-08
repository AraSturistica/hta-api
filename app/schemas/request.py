from datetime import date
from pydantic import BaseModel, Field, model_validator


class DatasetRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    fecha_valida_dias: date
    idsociedad: int = Field(gt=0)

    @model_validator(mode="after")
    def check(self) -> "DatasetRequest":
        if self.fecha_inicio > self.fecha_fin:
            raise ValueError("fecha_inicio debe ser <= fecha_fin")
        if self.fecha_valida_dias < self.fecha_fin:
            raise ValueError("fecha_valida_dias debe ser >= fecha_fin")
        return self
