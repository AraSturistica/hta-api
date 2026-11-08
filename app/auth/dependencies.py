from fastapi import Header, HTTPException, Request
from app.auth.api_keys import KeyData


async def get_current_key(request: Request, x_api_key: str | None = Header(default=None)) -> KeyData:
    if not x_api_key:
        raise HTTPException(401, "Credenciales inválidas")
    kd = request.app.state.keystore.verify(x_api_key)
    if kd is None:
        raise HTTPException(401, "Credenciales inválidas")
    return kd
