from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.document_storage import delete_stored_document, store_document
from app.database import get_db
from app.models import Document, Notebook, User
from app.rag.ingestion import ingest_text_document
from app.rag.vector_store import delete_document_vectors

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
ALLOWED_EXTENSIONS = {".txt", ".py", ".pdf", ".docx", ".pptx"}
MAX_DOCUMENT_SIZE = 25 * 1024 * 1024


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_document(
    notebook_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebook = db.scalar(select(Notebook).where(
        Notebook.id == notebook_id,
        Notebook.user_id == current_user.id,
    ))
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only TXT, Python, PDF, DOCX, and PPTX files are supported.")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    safe_filename = Path(file.filename.replace("\\", "/")).name
    if not safe_filename or len(safe_filename) > 255:
        raise HTTPException(status_code=400, detail="Filename must be 255 characters or fewer.")
    file_content = file.file.read(MAX_DOCUMENT_SIZE + 1)
    if len(file_content) > MAX_DOCUMENT_SIZE:
        raise HTTPException(status_code=413, detail="Document size must not exceed 25 MB.")
    if extension == ".pdf" and b"%PDF-" not in file_content[:1024]:
        raise HTTPException(status_code=400, detail="The uploaded file does not contain a valid PDF header.")
    if extension in {".docx", ".pptx"} and not file_content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="The uploaded Office document is not a valid ZIP-based file.")
    if extension == ".txt":
        try:
            file_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Text files must use UTF-8 encoding.") from exc
    if extension == ".py":
        try:
            file_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Python source files must use UTF-8 encoding.") from exc

    stored_filename = f"{uuid4().hex}{extension}"
    storage_path: str | None = None
    temporary_ingestion_file: Path | None = None
    document: Document | None = None
    try:
        storage_path = store_document(
            user_id=current_user.id,
            notebook_id=notebook.id,
            filename=stored_filename,
            content=file_content,
            content_type=file.content_type or {
                ".pdf": "application/pdf",
                ".py": "text/x-python",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }.get(extension, "text/plain"),
            local_upload_dir=UPLOAD_DIR,
        )
        if storage_path.startswith("supabase://"):
            with NamedTemporaryFile(suffix=extension, delete=False) as temporary_file:
                temporary_file.write(file_content)
                temporary_ingestion_file = Path(temporary_file.name)
            ingestion_path = temporary_ingestion_file
        else:
            ingestion_path = Path(storage_path)
        document = Document(
            user_id=current_user.id,
            notebook_id=notebook.id,
            filename=safe_filename,
            document_type=extension.lstrip("."),
            storage_path=storage_path,
            processing_status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        ingest_text_document(
            file_path=ingestion_path,
            user_id=current_user.id,
            notebook_id=notebook.id,
            source_name=file.filename,
            document_id=document.id,
        )
        document.processing_status = "completed"
        db.commit()
        db.refresh(document)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        if document is not None and document.id is not None:
            try:
                persisted_document = db.get(Document, document.id)
                if persisted_document is not None:
                    db.delete(persisted_document)
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to remove incomplete document record")
        logger.exception("Document processing failed: %s", exc)
        if storage_path:
            try:
                delete_stored_document(storage_path)
            except Exception:
                logger.exception("Failed to clean up stored document after processing error")
        raise HTTPException(status_code=500, detail="Document processing failed")
    finally:
        if temporary_ingestion_file and temporary_ingestion_file.exists():
            temporary_ingestion_file.unlink()
    return {
        "id": document.id,
        "filename": document.filename,
        "document_type": document.document_type,
        "notebook_id": document.notebook_id,
        "processing_status": document.processing_status,
    }


@router.get("")
def get_documents(notebook_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notebook = db.scalar(select(Notebook).where(
        Notebook.id == notebook_id,
        Notebook.user_id == current_user.id,
    ))
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    documents = db.scalars(
        select(Document)
        .where(Document.notebook_id == notebook_id, Document.user_id == current_user.id)
        .order_by(Document.id.desc())
    ).all()
    return [
        {
            "id": document.id,
            "filename": document.filename,
            "document_type": document.document_type,
            "notebook_id": document.notebook_id,
            "processing_status": document.processing_status,
        }
        for document in documents
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.scalar(select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.processing_status in {"pending", "processing"}:
        raise HTTPException(status_code=409, detail="Wait for document processing to finish before deleting it.")
    try:
        delete_document_vectors(document.id)
        delete_stored_document(document.storage_path)
    except Exception as exc:
        logger.exception("Failed to delete document %s", document.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The document could not be fully deleted. Please try again.",
        ) from exc
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
