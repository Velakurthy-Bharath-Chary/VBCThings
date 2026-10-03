from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VBC Things"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    overpass_api_url: str | None = None
    nominatim_base_url: str | None = None
    document_storage_backend: Literal["local", "supabase"] = "local"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "notebook-documents"

    database_url: str
    jwt_secret: str
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = 60

    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"
    vision_model: str = "qwen/qwen3.8-27b"

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.environment.lower() == "production":
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 characters in production.")
            if not self.groq_api_key.strip():
                raise ValueError("GROQ_API_KEY is required in production.")
            if not self.overpass_api_url:
                raise ValueError("OVERPASS_API_URL must be explicitly configured in production.")
            if not self.nominatim_base_url or not self.nominatim_base_url.strip().startswith("https://"):
                raise ValueError("NOMINATIM_BASE_URL must be explicitly configured with HTTPS in production.")
            if (
                self.document_storage_backend != "supabase"
                or not self.supabase_url
                or not self.supabase_service_role_key
            ):
                raise ValueError("Production document storage requires Supabase Storage configuration.")
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError("Production CORS_ORIGINS must list explicit frontend origins.")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
