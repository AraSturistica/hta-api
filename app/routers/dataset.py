import asyncio
import csv
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from app.auth.api_keys import KeyData
from app.auth.dependencies import get_current_key
from app.schemas.request import DatasetRequest
from app.schemas.response import COLUMNS, DatasetRecord
from app.services.dataset_service import call_hta_sp

router = APIRouter(prefix="/api/v1")
log = logging.getLogger("hta")
NO_STORE = {"Cache-Control": "no-store, no-cache, private"}


@router.post("/dataset/hta")
async def dataset(req: DatasetRequest, request: Request, fmt: str = Query("json", pattern="^(json|csv)$"),
                  key: KeyData = Depends(get_current_key)):
    if req.idsociedad not in key.sociedades:
        raise HTTPException(403, "Clave no autorizada para esta sociedad")
    st = request.app.state
    wait = st.rate_limiter.check(key.key_id, key.rate_per_hour)
    if wait is not None:
        raise HTTPException(429, "Límite de solicitudes excedido", headers={"Retry-After": str(int(wait))})
    ck = f"{req.idsociedad}|{req.fecha_inicio}|{req.fecha_fin}|{req.fecha_valida_dias}"

    async def fetch() -> list[dict]:
        rows = await call_hta_sp(st.pool, st.sem, req, st.settings.db_query_timeout)
        return [DatasetRecord.model_validate(r).model_dump(mode="json") for r in rows]

    try:
        data, hit = await st.cache.get_or_fetch(ck, fetch)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Tiempo de consulta agotado")
    except HTTPException:
        raise
    except Exception:
        log.exception("error_dataset key_id=%s sociedad=%s", key.key_id, req.idsociedad)
        raise HTTPException(500, "Error interno")
    log.info("dataset key_id=%s sociedad=%s rows=%d cache=%s", key.key_id, req.idsociedad, len(data), hit)
    headers = {**NO_STORE, "X-Cache": "HIT" if hit else "MISS", "X-Row-Count": str(len(data))}
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(data)
        return Response(buf.getvalue(), media_type="text/csv", headers=headers)
    return JSONResponse(data, headers=headers)
