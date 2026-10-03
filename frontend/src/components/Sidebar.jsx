import { useEffect, useRef, useState } from 'react';

import {
  analyzeImageThroughOrchestrator,
  createNotebook,
  deleteDocument,
  getDocuments,
  getNotebooks,
  uploadDocument,
} from '../services/api';

import { getToken } from '../services/auth';

function Sidebar({ selectedNotebook, onNotebookSelect }) {
  const [notebooks, setNotebooks] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [documentsNotebookId, setDocumentsNotebookId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState(null);
  const [analyzingImage, setAnalyzingImage] = useState(false);
  const [error, setError] = useState('');

  const fileInputRef = useRef(null);
  const imageInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    getNotebooks(getToken())
      .then((data) => {
        if (!active) return;
        setNotebooks(data);
        if (data.length > 0) onNotebookSelect(data[0]);
      })
      .catch((err) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [onNotebookSelect]);

  useEffect(() => {
    if (!selectedNotebook) return undefined;
    let active = true;
    getDocuments(getToken(), selectedNotebook.id)
      .then((data) => {
        if (!active) return;
        setError('');
        setDocuments(data);
        setDocumentsNotebookId(selectedNotebook.id);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setDocuments([]);
        setDocumentsNotebookId(selectedNotebook.id);
      });
    return () => { active = false; };
  }, [selectedNotebook]);

  const visibleDocuments = documentsNotebookId === selectedNotebook?.id ? documents : [];
  const hasProcessingDocuments = visibleDocuments.some(
    (document) => ['pending', 'processing'].includes(document.processing_status),
  );

  useEffect(() => {
    if (!selectedNotebook || !hasProcessingDocuments) return undefined;
    let active = true;
    const interval = window.setInterval(() => {
      getDocuments(getToken(), selectedNotebook.id)
        .then((data) => {
          if (active) setDocuments(data);
        })
        .catch((err) => {
          if (active) setError(err.message);
        });
    }, 2000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [selectedNotebook, hasProcessingDocuments]);

  async function handleCreateNotebook() {
    const name = window.prompt('Enter notebook name:');

    if (!name?.trim()) {
      return;
    }

    try {
      setError('');

      const token = getToken();

      const notebook = await createNotebook(
        token,
        name.trim(),
        '',
      );

      setNotebooks((current) => [...current, notebook]);
      onNotebookSelect(notebook);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteDocument(document) {
    if (!window.confirm(`Delete “${document.filename}” and its indexed content?`)) return;
    setDeletingDocumentId(document.id);
    setError('');
    try {
      await deleteDocument(getToken(), document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingDocumentId(null);
    }
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0];

    if (!file || !selectedNotebook) {
      return;
    }

    try {
      setError('');
      setUploading(true);

      const token = getToken();

      await uploadDocument(
        token,
        selectedNotebook.id,
        file,
      );

      const refreshedDocuments = await getDocuments(token, selectedNotebook.id);
      setDocuments(refreshedDocuments);
      setDocumentsNotebookId(selectedNotebook.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }

  async function handleImageChange(event) {
    const file = event.target.files?.[0];

    if (!file || !selectedNotebook) {
      return;
    }

    try {
      setError('');
      setAnalyzingImage(true);

      const question = window.prompt(
        'What would you like me to analyze in this image?',
        'Explain what is shown in this image.',
      );

      if (!question?.trim()) {
        return;
      }

      const token = getToken();

      const result = await analyzeImageThroughOrchestrator(
        token,
        selectedNotebook.id,
        file,
        question.trim(),
      );

      window.dispatchEvent(
        new CustomEvent('image-analysis-complete', {
          detail: result,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzingImage(false);
      event.target.value = '';
    }
  }

  return (
    <aside className="bg-white h-100 p-3">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h2 className="h6 fw-bold mb-0">
          Sources
        </h2>

        <button
          type="button"
          className="btn btn-dark btn-sm"
          onClick={handleCreateNotebook}
        >
          + Notebook
        </button>
      </div>

      {error && (
        <div className="alert alert-danger small py-2">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center py-4">
          <div
            className="spinner-border spinner-border-sm"
            role="status"
          />
        </div>
      ) : notebooks.length === 0 ? (
        <div className="text-center text-muted py-5">
          <div className="fs-2 mb-2">
            📚
          </div>

          <p className="small mb-2">
            No notebooks yet.
          </p>

          <button
            type="button"
            className="btn btn-outline-dark btn-sm"
            onClick={handleCreateNotebook}
          >
            Create notebook
          </button>
        </div>
      ) : (
        <>
          <label
            htmlFor="notebook-select"
            className="form-label small fw-semibold"
          >
            Notebook
          </label>

          <select
            id="notebook-select"
            className="form-select form-select-sm mb-3"
            value={selectedNotebook?.id || ''}
            onChange={(event) => {
              const notebook = notebooks.find(
                (item) =>
                  item.id === Number(event.target.value),
              );

              if (notebook) {
                onNotebookSelect(notebook);
              }
            }}
          >
            {notebooks.map((notebook) => (
              <option
                key={notebook.id}
                value={notebook.id}
              >
                {notebook.name}
              </option>
            ))}
          </select>

          {/* Document upload */}

          <input
            ref={fileInputRef}
            type="file"
            className="d-none"
            accept=".pdf,.txt,.docx,.pptx"
            onChange={handleFileChange}
          />

          <button
            type="button"
            className="btn btn-outline-dark btn-sm w-100 mb-2"
            disabled={
              !selectedNotebook ||
              uploading ||
              analyzingImage
            }
            onClick={() =>
              fileInputRef.current?.click()
            }
          >
            {uploading
              ? 'Uploading...'
              : '+ Upload source'}
          </button>

          {/* Image analysis */}

          <input
            ref={imageInputRef}
            type="file"
            className="d-none"
            accept=".jpg,.jpeg,.png,.webp"
            onChange={handleImageChange}
          />

          <button
            type="button"
            className="btn btn-outline-primary btn-sm w-100 mb-3"
            disabled={
              !selectedNotebook ||
              uploading ||
              analyzingImage
            }
            onClick={() =>
              imageInputRef.current?.click()
            }
          >
            {analyzingImage
              ? 'Analyzing image...'
              : '+ Analyze Image'}
          </button>

          <div className="border-top pt-3">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h3 className="small fw-semibold mb-0">
                Documents
              </h3>

              {visibleDocuments.length > 0 && (
                <span className="badge text-bg-light">
                  {visibleDocuments.length}
                </span>
              )}
            </div>

            {selectedNotebook && documentsNotebookId !== selectedNotebook.id ? (
              <div className="text-center py-3">
                <div
                  className="spinner-border spinner-border-sm"
                  role="status"
                />
              </div>
            ) : visibleDocuments.length === 0 ? (
              <p className="small text-muted mb-0">
                No documents uploaded yet.
              </p>
            ) : (
              <div className="d-flex flex-column gap-2">
                {visibleDocuments.map((document) => (
                  <div
                    key={document.id}
                    className="border rounded-2 p-2"
                  >
                    <div className="d-flex align-items-start justify-content-between gap-2">
                      <div className="d-flex align-items-start gap-2 min-width-0">
                      <span>
                        {document.document_type === 'pdf'
                          ? '📄'
                          : '📝'}
                      </span>

                      <div className="min-width-0">
                        <div
                          className="small fw-semibold text-truncate"
                          title={document.filename}
                        >
                          {document.filename}
                        </div>

                        <div className="small text-muted">
                          {document.processing_status}
                        </div>
                      </div>
                      </div>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-danger px-2 flex-shrink-0 source-delete-button"
                        disabled={deletingDocumentId === document.id || ['pending', 'processing'].includes(document.processing_status)}
                        onClick={() => void handleDeleteDocument(document)}
                        aria-label={`Delete ${document.filename}`}
                        title={['pending', 'processing'].includes(document.processing_status) ? 'Available after processing' : 'Delete source'}
                      >
                        {deletingDocumentId === document.id ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

export default Sidebar;

// FILE PURPOSE:
// Provides notebook selection, notebook creation, document upload,
// orchestrated image analysis, and notebook-scoped source listing.
