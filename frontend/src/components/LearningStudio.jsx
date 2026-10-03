import { useEffect, useState } from 'react';

import {
  deleteStudioArtifact,
  generateStudioArtifact,
  getStudioArtifacts,
  getStudioProgress,
} from '../services/api';

import { getToken } from '../services/auth';

const ARTIFACT_TYPES = [
  {
    type: 'notes',
    label: 'Notes',
    icon: '📝',
  },
  {
    type: 'summary',
    label: 'Summary',
    icon: '📋',
  },
  {
    type: 'flashcards',
    label: 'Flashcards',
    icon: '🎴',
  },
  {
    type: 'quiz',
    label: 'Quiz',
    icon: '❓',
  },
  {
    type: 'study_guide',
    label: 'Study Guide',
    icon: '📚',
  },
];

function hasInteractiveQuiz(content) {
  try {
    const parsed = JSON.parse(String(content || '').replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, ''));
    return Array.isArray(parsed.questions) && parsed.questions.length > 0;
  } catch {
    return false;
  }
}

function LearningStudio({ notebook, onOpenArtifact, refreshToken = 0 }) {
  const [artifacts, setArtifacts] = useState([]);
  const [loadedNotebookId, setLoadedNotebookId] = useState(null);
  const [generating, setGenerating] = useState('');
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(null);
  const [openingArtifactId, setOpeningArtifactId] = useState(null);

  useEffect(() => {
    if (!notebook) return undefined;
    let active = true;
    Promise.all([
      getStudioArtifacts(getToken(), notebook.id),
      getStudioProgress(getToken(), notebook.id),
    ])
      .then(([data, progressData]) => {
        if (!active) return;
        setError('');
        setArtifacts(data);
        setProgress(progressData);
        setLoadedNotebookId(notebook.id);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setArtifacts([]);
        setProgress(null);
        setLoadedNotebookId(notebook.id);
      });
    return () => { active = false; };
  }, [notebook, refreshToken]);

  const visibleArtifacts = loadedNotebookId === notebook?.id ? artifacts : [];
  const isLoadingArtifacts = Boolean(notebook && loadedNotebookId !== notebook.id);

  async function handleGenerate(artifactType) {
    if (!notebook || generating) {
      return;
    }

    try {
      setError('');
      setGenerating(artifactType);

      const token = getToken();

      const artifact = await generateStudioArtifact(
        token,
        notebook.id,
        artifactType,
      );

      setArtifacts((current) => [
        artifact,
        ...current,
      ]);
      onOpenArtifact?.(artifact);
      setProgress(await getStudioProgress(token, notebook.id));
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating('');
    }
  }

  async function handleDelete(artifactId) {
    try {
      setError('');

      const token = getToken();

      await deleteStudioArtifact(
        token,
        artifactId,
      );

      setArtifacts((current) =>
        current.filter(
          (artifact) => artifact.id !== artifactId,
        ),
      );
      setProgress(await getStudioProgress(getToken(), notebook.id));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleOpenArtifact(artifact) {
    if (artifact.artifact_type !== 'quiz' || hasInteractiveQuiz(artifact.content)) {
      onOpenArtifact?.(artifact);
      return;
    }

    try {
      setError('');
      setOpeningArtifactId(artifact.id);
      const interactiveQuiz = await generateStudioArtifact(
        getToken(), notebook.id, 'quiz', artifact.title,
      );
      setArtifacts((current) => [interactiveQuiz, ...current]);
      onOpenArtifact?.(interactiveQuiz);
      setProgress(await getStudioProgress(getToken(), notebook.id));
    } catch (err) {
      setError(err.message || 'Could not convert this saved quiz to an interactive quiz.');
    } finally {
      setOpeningArtifactId(null);
    }
  }

  return (
    <aside className="border-start bg-white h-100 p-3 overflow-auto">
      <div className="mb-3">
        <h2 className="h6 fw-bold mb-1">
          Learning Studio
        </h2>

        <p className="text-muted small mb-0">
          {notebook
            ? `Create study material from ${notebook.name}.`
            : 'Select a notebook first.'}
        </p>
      </div>

      {error && (
        <div className="alert alert-danger small py-2">
          {error}
        </div>
      )}

      {progress && loadedNotebookId === notebook?.id && (
        <section className="border rounded-2 p-2 mb-3" aria-label="Learning progress">
          <h3 className="small fw-semibold mb-2">Notebook progress</h3>
          <div className="row g-2 text-center">
            <div className="col-4"><div className="fw-bold">{progress.source_count}</div><div className="small text-muted">Sources</div></div>
            <div className="col-4"><div className="fw-bold">{progress.conversation_count}</div><div className="small text-muted">Chats</div></div>
            <div className="col-4"><div className="fw-bold">{progress.artifact_count}</div><div className="small text-muted">Artifacts</div></div>
          </div>
          <div className="small d-flex justify-content-between mt-2">
            <span>Quiz attempts</span>
            <span>{progress.quiz_attempt_count}{progress.average_quiz_score_percent !== null ? ` · ${progress.average_quiz_score_percent}% average` : ''}</span>
          </div>
          {progress.recommendations?.length > 0 && (
            <div className="mt-3">
              <h4 className="small fw-semibold mb-1">Suggested next steps</h4>
              <ul className="small text-muted ps-3 mb-0">
                {progress.recommendations.map((recommendation) => (
                  <li key={recommendation.key} className="mb-1">
                    <strong>{recommendation.title}:</strong> {recommendation.detail}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      <div className="d-grid gap-2 mb-4">
        {ARTIFACT_TYPES.map((artifact) => {
          const isGenerating =
            generating === artifact.type;

          return (
            <button
              key={artifact.type}
              type="button"
              className="btn btn-outline-dark text-start"
              disabled={!notebook || Boolean(generating)}
              onClick={() =>
                handleGenerate(artifact.type)
              }
            >
              {isGenerating ? (
                <>
                  <span
                    className="spinner-border spinner-border-sm me-2"
                    role="status"
                  />

                  Generating...
                </>
              ) : (
                <>
                  <span className="me-2">
                    {artifact.icon}
                  </span>

                  {artifact.label}
                </>
              )}
            </button>
          );
        })}
      </div>

      <div className="border-top pt-3">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <h3 className="small fw-semibold mb-0">
            Your Artifacts
          </h3>

          {visibleArtifacts.length > 0 && (
            <span className="badge text-bg-light">
              {visibleArtifacts.length}
            </span>
          )}
        </div>

        {isLoadingArtifacts ? (
          <div className="text-center py-3">
            <div
              className="spinner-border spinner-border-sm"
              role="status"
            />
          </div>
        ) : visibleArtifacts.length === 0 ? (
          <p className="small text-muted">
            No learning artifacts yet.
          </p>
        ) : (
          <div className="d-flex flex-column gap-3">
            {visibleArtifacts.map((artifact) => (
              <div
                key={artifact.id}
                className="card border-0 bg-light"
              >
                <div className="card-body p-3">
                  <div className="d-flex justify-content-between align-items-start gap-2">
                    <div>
                      <h4 className="small fw-bold mb-1">
                        {artifact.title}
                      </h4>

                      <span className="badge text-bg-secondary">
                        {artifact.artifact_type}
                      </span>
                    </div>

                    <div className="d-flex align-items-center gap-2">
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-dark"
                        onClick={() => void handleOpenArtifact(artifact)}
                        disabled={openingArtifactId === artifact.id}
                      >
                          {openingArtifactId === artifact.id
                            ? 'Making interactive…'
                            : artifact.artifact_type === 'quiz' && !hasInteractiveQuiz(artifact.content)
                              ? 'Make interactive'
                              : 'Open in chat'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-danger"
                        onClick={() => handleDelete(artifact.id)}
                        aria-label={`Delete ${artifact.title}`}
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  <p className="small text-muted mt-3 mb-0">
                    Open this {artifact.artifact_type.replace('_', ' ')} in the chat workspace for a full view.
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}

export default LearningStudio;

// FILE PURPOSE:
// Provides the Learning Studio interface for generating, viewing,
// and deleting notebook-scoped learning artifacts.

// FILE PURPOSE:
// Provides the Learning Studio panel for generating and accessing
// personalized study artifacts.
