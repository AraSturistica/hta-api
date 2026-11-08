import asyncio
from typing import Any
import aiomysql
from app.schemas.request import DatasetRequest

SP_SQL = "CALL SP_Procesos_dataset_pacientes_HTA(%s, %s, %s, %s)"


async def call_hta_sp(pool: Any, sem: asyncio.Semaphore, req: DatasetRequest, timeout: float) -> list[dict]:
    async with sem:
        async with pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await asyncio.wait_for(
                        cur.execute(SP_SQL, (req.fecha_inicio, req.fecha_fin, req.fecha_valida_dias, req.idsociedad)),
                        timeout=timeout,
                    )
                    rows = list(await cur.fetchall())
                    while await cur.nextset():
                        await cur.fetchall()
                return rows
            except asyncio.TimeoutError:
                conn.close()  # conexión en estado incierto: no se reutiliza
                raise
            finally:
                if not conn.closed:
                    await conn.rollback()
