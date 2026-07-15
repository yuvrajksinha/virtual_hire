"""Application settings, loaded from environment variables / .env.

VHIRE-5. See .env.example for the full variable reference and
docs/07-technical-stack.md for why each dependency exists.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated view of the process environment.

    Fields with no default are required — the app should fail fast at
    startup if a core infrastructure dependency (Postgres, Qdrant, Redis)
    isn't configured, rather than failing later at first use.

    Fields with a blank/placeholder default belong to integrations not
    yet wired into any epic (auth provider, AI providers, email, S3
    credentials) — present so every consumer can import one Settings
    shape from day one, per docs/06-architecture.md's component list.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    environment: str = "development"

    # Postgres (relational data only) - docs/05-data-model.md
    database_url: str

    # Qdrant (vector store, one collection per Organization) - docs/05-data-model.md, docs/07-technical-stack.md
    qdrant_url: str
    qdrant_api_key: str = ""

    # Redis (Celery broker/backend) - docs/07-technical-stack.md
    redis_url: str

    # Object storage (S3-compatible) - docs/06-architecture.md multi-tenancy section
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "sift-resumes-dev"

    # Auth provider (Auth0/Clerk) - HR user sessions, org_id claim feeds RLS session var
    auth_jwks_url: str = ""
    auth_jwt_issuer: str = ""
    auth_jwt_audience: str = ""

    # AI providers - docs/07-technical-stack.md multi-model crew assignment
    anthropic_api_key: str = ""
    voyage_api_key: str = ""

    # Email delivery (transactional)
    email_provider_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings instance, parsed once and cached.

    Every call site should go through this accessor rather than
    instantiating Settings() directly, so the environment is only read
    and validated a single time per process.

    Raises:
        pydantic.ValidationError: if a required field (database_url,
            qdrant_url, redis_url) is missing from the environment/.env.
    """
    return Settings()
