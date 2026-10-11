import os
from functools import lru_cache
from typing import Dict, List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Environment & Server
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # API Metadata
    API_TITLE: str = "Customer Journey Analytics API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # API Security
    API_KEY: str = "development-secret-key-change-in-production"
    API_KEY_NAME: str = "X-API-Key"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # BigQuery Configuration
    GCP_PROJECT_ID: str = "rangkul-355bb"
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    BQ_DATASET: str = "analytics_journey"
    BQ_EVENTS_TABLE: str = "rangkul-355bb.analytics_journey.raw_events_agustus_september"
    BQ_CUSTOMERS_TABLE: str = "rangkul-355bb.analytics_journey.all_customer_rangkul"

    # Query Performance & Cost Protection
    BQ_MAX_BYTES_BILLED: Optional[int] = 10737418240  # 10 GB default
    BQ_QUERY_TIMEOUT_SECONDS: int = 60

    # Pagination Constraints
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100

    # Customer Column Allowlist & Mapping (logical_name: bq_column_name)
    CUSTOMER_COLUMN_MAPPING: Dict[str, str] = Field(
        default_factory=lambda: {
            "role": "role",
            "depo": "depo",
            "region": "region",
            "area": "area",
        }
    )

    @field_validator("BQ_EVENTS_TABLE", "BQ_CUSTOMERS_TABLE", mode="before")
    @classmethod
    def clean_table_name(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            insecure_defaults = {
                "development-secret-key-change-in-production",
                "change-this-in-production",
                "",
            }
            if self.API_KEY in insecure_defaults:
                raise ValueError(
                    "FATAL SECURITY ERROR: Pada mode production, API_KEY wajib diisi dengan nilai rahasia "
                    "yang kuat dan tidak boleh menggunakan nilai default."
                )
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def customer_fields(self) -> List[str]:
        return list(self.CUSTOMER_COLUMN_MAPPING.keys())


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
