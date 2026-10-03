import { useState } from 'react';
import { analyzeImageThroughOrchestrator } from '../services/api';
import { getToken } from '../services/auth';

function ImageAnalyzer({ notebook }) {
  const [file, setFile] = useState(null);
  const [question, setQuestion] = useState(
    'Explain what is shown in this image.'
  );
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!notebook) {
      setError('Please select a notebook first.');
      return;
    }

    if (!file) {
      setError('Please select an image.');
      return;
    }

    setLoading(true);
    setError('');
    setAnswer('');

    try {
      const data = await analyzeImageThroughOrchestrator(
        getToken(), notebook.id, file, question.trim(),
      );
      setAnswer(data.answer);
      window.dispatchEvent(new CustomEvent('image-analysis-complete', {
        detail: { ...data, notebook_id: notebook.id },
      }));
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-3">
      <h5 className="mb-3">Image Analysis</h5>

      {!notebook ? (
        <div className="alert alert-secondary">
          Select a notebook to analyze an image.
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="form-label">
              Image
            </label>

            <input
              type="file"
              className="form-control"
              accept=".jpg,.jpeg,.png,.webp"
              onChange={(event) => {
                setFile(event.target.files?.[0] || null);
                setAnswer('');
                setError('');
              }}
            />
          </div>

          <div className="mb-3">
            <label className="form-label">
              Question
            </label>

            <textarea
              className="form-control"
              rows="3"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask something about the image..."
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary w-100"
            disabled={loading}
          >
            {loading ? 'Analyzing...' : 'Analyze Image'}
          </button>
        </form>
      )}

      {error && (
        <div className="alert alert-danger mt-3">
          {error}
        </div>
      )}

      {answer && (
        <div className="card mt-3">
          <div className="card-body">
            <h6 className="card-title">Vision Response</h6>
            <div style={{ whiteSpace: 'pre-wrap' }}>
              {answer}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ImageAnalyzer;

// FILE PURPOSE:
// Provides the VBC Things frontend interface for uploading an image,
// asking a question through the orchestrator, and sending the resulting
// explanation to the tutor conversation.
