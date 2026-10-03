from pathlib import Path
from unittest.mock import Mock

from app.core import document_storage


def test_supabase_document_upload_uses_private_storage_rest_endpoint(monkeypatch):
    monkeypatch.setattr(document_storage.settings, "document_storage_backend", "supabase")
    monkeypatch.setattr(document_storage.settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(document_storage.settings, "supabase_service_role_key", "test-secret")
    monkeypatch.setattr(document_storage.settings, "supabase_storage_bucket", "private-docs")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        response = Mock()
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr(document_storage.httpx, "post", fake_post)
    path = document_storage.store_document(4, 7, "file name.txt", b"content", "text/plain")

    assert path == "supabase://private-docs/4/7/file name.txt"
    assert calls[0][0] == "https://project.supabase.co/storage/v1/object/private-docs/4/7/file%20name.txt"
    assert calls[0][1]["content"] == b"content"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-secret"
    assert calls[0][1]["headers"]["x-upsert"] == "false"

    document_storage.store_document(4, 7, "file name.txt", b"content", "text/plain", upsert=True)
    assert calls[1][1]["headers"]["x-upsert"] == "true"


def test_local_document_upload_honors_upload_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(document_storage.settings, "document_storage_backend", "local")
    path = Path(document_storage.store_document(2, 5, "document.txt", b"text", "text/plain", tmp_path))
    assert path == tmp_path / "2" / "document.txt"
    assert path.read_bytes() == b"text"
    document_storage.delete_stored_document(str(path))
    assert not path.exists()


def test_supabase_document_delete_uses_object_reference(monkeypatch):
    monkeypatch.setattr(document_storage.settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(document_storage.settings, "supabase_service_role_key", "test-secret")
    calls = []

    def fake_delete(url, **kwargs):
        calls.append((url, kwargs))
        response = Mock()
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr(document_storage.httpx, "delete", fake_delete)
    document_storage.delete_stored_document("supabase://private-docs/4/7/file name.txt")
    assert calls[0][0] == "https://project.supabase.co/storage/v1/object/private-docs/4/7/file%20name.txt"
    assert calls[0][1]["headers"]["apikey"] == "test-secret"
