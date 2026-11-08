import ssl
import aiomysql
from app.config import Settings


def build_ssl(settings: Settings) -> ssl.SSLContext | None:
    if not settings.db_ssl_ca:
        if settings.environment == "production":
            raise RuntimeError("DB_SSL_CA obligatorio en producción")
        return None
    ctx = ssl.create_default_context(cafile=settings.db_ssl_ca)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


async def create_pool(settings: Settings) -> aiomysql.Pool:
    return await aiomysql.create_pool(
        host=settings.db_host, port=settings.db_port, user=settings.db_user,
        password=settings.db_password, db=settings.db_name, minsize=1,
        maxsize=settings.db_pool_max, connect_timeout=settings.db_connect_timeout,
        ssl=build_ssl(settings), autocommit=False, pool_recycle=1800, charset="utf8mb4",
    )
