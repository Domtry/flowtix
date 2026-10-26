from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "FLOWTIX_"}

    database_url: str = "postgresql+asyncpg://flowtix:flowtix@localhost:5432/flowtix"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15

    cors_origins: list[str] = ["http://localhost:4200"]


settings = Settings()
