from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import httpx

from app.config import settings


LOCAL_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
SUPABASE_SCHEME = "supabase://"


def _supabase_headers(content_type: str | None = None) -> dict[str, str]:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase Storage is not configured.")
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _storage_url(bucket: str, object_path: str) -> str:
    encoded_bucket = quote(bucket, safe="")
    encoded_path = quote(object_path.lstrip("/"), safe="/")
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{encoded_bucket}/{encoded_path}"


def store_document(
    user_id: int,
    notebook_id: int,
    filename: str,
    content: bytes,
    content_type: str,
    local_upload_dir: Path | None = None,
    upsert: bool = False,
) -> str:
    if settings.document_storage_backend == "local":
        upload_dir = (local_upload_dir or LOCAL_UPLOAD_DIR) / str(user_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / filename
        path.write_bytes(content)
        return str(path)

    object_path = f"{user_id}/{notebook_id}/{filename}"
    response = httpx.post(
        _storage_url(settings.supabase_storage_bucket, object_path),
        content=content,
        headers={
            **_supabase_headers(content_type),
            "x-upsert": "true" if upsert else "false",
        },
        timeout=httpx.Timeout(30.0, connect=5.0),
    )
    response.raise_for_status()
    return f"{SUPABASE_SCHEME}{settings.supabase_storage_bucket}/{object_path}"


def delete_stored_document(storage_path: str) -> None:
    if storage_path.startswith(SUPABASE_SCHEME):
        bucket_and_path = storage_path[len(SUPABASE_SCHEME):]
        bucket, separator, object_path = bucket_and_path.partition("/")
        if not separator or not bucket or not object_path:
            raise ValueError("Invalid Supabase document storage reference.")
        response = httpx.delete(
            _storage_url(bucket, object_path),
            headers=_supabase_headers(),
            timeout=httpx.Timeout(15.0, connect=5.0),
        )
        response.raise_for_status()
        return

    path = Path(storage_path)
    if path.exists():
        path.unlink()


def materialize_stored_document(storage_path: str, suffix: str) -> Path:
    """Copy a stored document to a temporary path for an ingestion worker."""
    if storage_path.startswith(SUPABASE_SCHEME):
        bucket_and_path = storage_path[len(SUPABASE_SCHEME):]
        bucket, separator, object_path = bucket_and_path.partition("/")
        if not separator or not bucket or not object_path:
            raise ValueError("Invalid Supabase document storage reference.")
        response = httpx.get(
            _storage_url(bucket, object_path),
            headers=_supabase_headers(),
            timeout=httpx.Timeout(60.0, connect=5.0),
        )
        response.raise_for_status()
        content = response.content
    else:
        path = Path(storage_path).resolve()
        root = LOCAL_UPLOAD_DIR.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Stored document path is outside the configured upload directory.")
        content = path.read_bytes()

    with NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(content)
        return Path(temporary_file.name)


# FILE PURPOSE:
# Stores validated notebook documents on local disk or in a private
# Supabase Storage bucket, materializes owner-stored files for workers,
# and removes failed-upload objects safely.
