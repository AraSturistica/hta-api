import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.auth.api_keys import KeyStore
from app.config import Settings, get_settings
from app.routers.dataset import router
from app.services.cache import HTACache
from app.services.rate_limiter import RateLimiter


def create_app(settings: Settings | None = None, pool=None, keystore: KeyStore | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        st = app.state
        st.settings = settings
        st.keystore = keystore or KeyStore.from_file(settings.api_keys_file)
        st.cache = HTACache(settings.cache_ttl_seconds, settings.cache_max_entries)
        st.rate_limiter = RateLimiter()
        st.sem = asyncio.Semaphore(settings.max_concurrent_sp)
        own = pool is None
        if own:
            from app.db.pool import create_pool
            st.pool = await create_pool(settings)
        else:
            st.pool = pool
        yield
        if own:
            st.pool.close()
            await st.pool.wait_closed()

    docs = "/docs" if settings.docs_enabled else None
    app = FastAPI(title="HTA Dataset API", lifespan=lifespan, docs_url=docs,
                  redoc_url=None, openapi_url="/openapi.json" if docs else None)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


def _factory() -> FastAPI:
    return create_app()
