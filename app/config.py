from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "api_hta"
    db_password: str = ""
    db_name: str = "clinicas"
    db_ssl_ca: str = ""
    db_pool_max: int = 10
    db_connect_timeout: int = 10
    db_query_timeout: float = 60.0
    max_concurrent_sp: int = 8
    cache_ttl_seconds: int = 600
    cache_max_entries: int = 200
    api_keys_file: str = "config/api_keys.json"
    docs_enabled: bool = False
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
