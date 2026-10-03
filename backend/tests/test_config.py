import pytest
from pydantic import ValidationError

from app.config import Settings


def production_settings(**overrides):
    values = {
        "database_url": "postgresql+psycopg://db.example/learning",
        "jwt_secret": "s" * 40,
        "groq_api_key": "groq-test-key",
        "environment": "production",
        "overpass_api_url": "https://overpass.example/api/interpreter",
        "nominatim_base_url": "https://nominatim.example",
        "document_storage_backend": "supabase",
        "supabase_url": "https://project.supabase.co",
        "supabase_service_role_key": "test-service-role-key",
        "cors_origins": "https://study.example",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_accepts_secure_required_settings():
    settings = production_settings()
    assert settings.allowed_origins == ["https://study.example"]


@pytest.mark.parametrize(
    "override",
    [
        {"jwt_secret": "short"},
        {"overpass_api_url": None},
        {"nominatim_base_url": None},
        {"document_storage_backend": "local"},
        {"supabase_service_role_key": None},
        {"cors_origins": "*"},
        {"groq_api_key": " "},
    ],
)
def test_production_configuration_rejects_missing_security_requirements(override):
    with pytest.raises(ValidationError):
        production_settings(**override)
