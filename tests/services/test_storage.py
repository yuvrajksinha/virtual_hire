"""Tests for app.services.storage (VHIRE-13 / E4): namespaced object keys
and the boto3 wrapper. Uses a fake S3 client rather than live AWS.
"""

import uuid

from app.services import storage


def test_object_key_for_resume_is_namespaced_by_org_and_resume():
    org_id = uuid.uuid4()
    resume_id = uuid.uuid4()

    key = storage.object_key_for_resume(org_id, resume_id, "resume.pdf")

    assert key == f"{org_id}/{resume_id}/resume.pdf"


class _FakeS3Client:
    def __init__(self):
        self.put_calls: list[dict] = []
        self.presign_calls: list[dict] = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def generate_presigned_url(self, operation, **kwargs):
        self.presign_calls.append({"operation": operation, **kwargs})
        return f"https://signed.example.test/{kwargs['Params']['Key']}"


def test_upload_object_puts_to_the_configured_bucket(monkeypatch):
    fake_client = _FakeS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: fake_client)

    storage.upload_object(key="org/resume/file.pdf", content=b"pdf-bytes")

    assert fake_client.put_calls[0]["Key"] == "org/resume/file.pdf"
    assert fake_client.put_calls[0]["Body"] == b"pdf-bytes"


def test_generate_signed_url_returns_a_url_for_the_key(monkeypatch):
    fake_client = _FakeS3Client()
    monkeypatch.setattr(storage, "get_s3_client", lambda: fake_client)

    url = storage.generate_signed_url("org/resume/file.pdf")

    assert url.endswith("org/resume/file.pdf")
    assert fake_client.presign_calls[0]["ExpiresIn"] == 3600
