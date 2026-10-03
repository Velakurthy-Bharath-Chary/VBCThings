from pathlib import Path

import pytest

from scripts import migrate_local_documents_to_supabase


def test_document_migration_accepts_only_files_under_upload_root(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    accepted = upload_root / "2" / "11" / "document.pdf"
    monkeypatch.setattr(migrate_local_documents_to_supabase, "LOCAL_UPLOAD_DIR", upload_root)

    assert migrate_local_documents_to_supabase._local_document_path(str(accepted)) == accepted.resolve()
    with pytest.raises(ValueError, match="outside"):
        migrate_local_documents_to_supabase._local_document_path(str(tmp_path / "other.pdf"))


# FILE PURPOSE:
# Verifies the Supabase migration only reads local document files within the configured upload root.
