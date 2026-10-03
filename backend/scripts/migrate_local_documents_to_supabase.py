from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.core.document_storage import LOCAL_UPLOAD_DIR, SUPABASE_SCHEME, store_document
from app.database import SessionLocal
from app.models import Document


CONTENT_TYPES = {
    "pdf": "application/pdf",
    "txt": "text/plain",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _local_document_path(storage_path: str) -> Path:
    path = Path(storage_path).resolve()
    root = LOCAL_UPLOAD_DIR.resolve()
    if not path.is_relative_to(root):
        raise ValueError("A document path is outside the configured local upload directory.")
    return path


def migrate_local_documents(batch_size: int = 25) -> int:
    if settings.document_storage_backend != "supabase":
        raise RuntimeError("Set DOCUMENT_STORAGE_BACKEND=supabase before running this migration.")
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase Storage credentials are not configured.")

    migrated = 0
    last_id = 0
    with SessionLocal() as db:
        while True:
            batch = db.scalars(
                select(Document)
                .where(Document.id > last_id)
                .order_by(Document.id)
                .limit(batch_size)
            ).all()
            if not batch:
                break

            for document in batch:
                last_id = document.id
                if document.storage_path.startswith(SUPABASE_SCHEME):
                    continue

                local_path = _local_document_path(document.storage_path)
                if not local_path.is_file():
                    raise FileNotFoundError(f"Local file for document {document.id} is missing.")
                content_type = CONTENT_TYPES.get(document.document_type.lower())
                if content_type is None:
                    raise ValueError(f"Unsupported stored document type for document {document.id}.")

                remote_path = store_document(
                    user_id=document.user_id,
                    notebook_id=document.notebook_id,
                    filename=local_path.name,
                    content=local_path.read_bytes(),
                    content_type=content_type,
                    upsert=True,
                )
                document.storage_path = remote_path
                db.commit()
                migrated += 1

    return migrated


if __name__ == "__main__":
    migrated_count = migrate_local_documents()
    print(f"Updated {migrated_count} document storage references to Supabase.")
    print("Local source files were retained for rollback.")


# FILE PURPOSE:
# Copies locally stored user documents to a private Supabase bucket and
# updates database references only after each successful upload.
