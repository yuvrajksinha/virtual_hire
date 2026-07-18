"""S3-compatible object storage wrapper. See docs/06-architecture.md's
multi-tenancy section: files are namespaced `{organization_id}/{resume_id}/{filename}`
and retrieved only via a time-limited signed URL, never a public path.

VHIRE-13 (E4). boto3 is synchronous - callers running inside an async
request/task should offload calls here to a thread (e.g.
`starlette.concurrency.run_in_threadpool`) rather than block the event loop.
"""

import uuid
from functools import lru_cache

import boto3

from app.core.config import get_settings


@lru_cache
def get_s3_client():
    """Return the process-wide boto3 S3 client, constructed once and cached."""
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def object_key_for_resume(organization_id: uuid.UUID, resume_id: uuid.UUID, filename: str) -> str:
    """Return the namespaced object key for one resume file."""
    return f"{organization_id}/{resume_id}/{filename}"


def upload_object(*, key: str, content: bytes) -> None:
    """Upload `content` to `key` in the configured resume bucket."""
    settings = get_settings()
    get_s3_client().put_object(Bucket=settings.s3_bucket_name, Key=key, Body=content)


def download_object(key: str) -> bytes:
    """Download and return the raw bytes stored at `key`. Used by the
    Parsing Worker (E6) to fetch a resume file before text extraction.
    """
    settings = get_settings()
    response = get_s3_client().get_object(Bucket=settings.s3_bucket_name, Key=key)
    return response["Body"].read()


def generate_signed_url(key: str, *, expires_in: int = 3600) -> str:
    """Return a time-limited signed URL for retrieving `key` (default 1 hour)."""
    settings = get_settings()
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )
