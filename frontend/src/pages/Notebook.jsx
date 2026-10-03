import { useCallback, useState } from 'react';

import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import TutorChat from '../components/TutorChat';
import LearningStudio from '../components/LearningStudio';
import ImageAnalyzer from '../components/ImageAnalyzer';
import SpeechStudio from '../components/SpeechStudio';
import NearbyResources from '../components/NearbyResources';
import { generateStudioArtifact } from '../services/api';
import { getToken } from '../services/auth';

function NotebookNotes({ notebook }) {
  const [notes, setNotes] = useState(() => (
    notebook ? localStorage.getItem(`notebook-notes-${notebook.id}`) || '' : ''
  ));
  const [saved, setSaved] = useState(false);

  function updateNotes(value) {
    setNotes(value);
    if (!notebook) return;
    localStorage.setItem(`notebook-notes-${notebook.id}`, value);
    setSaved(true);
  }

  return (
    <section className="notebook-notes" aria-labelledby="notebook-notes-title">
      <div className="d-flex justify-content-between align-items-center mb-2">
        <div>
          <h2 className="h5 fw-bold mb-1" id="notebook-notes-title">My notes</h2>
          <p className="small text-muted mb-0">Write anything you want to remember. Notes save in this browser for this notebook.</p>
        </div>
        <span className="small text-muted" aria-live="polite">{saved ? 'Saved' : ''}</span>
      </div>
      <textarea
        className="form-control notebook-notes-input"
        aria-label="Personal notebook notes"
        placeholder={notebook ? 'Start writing your notes…' : 'Select a notebook to take notes.'}
        value={notes}
        onChange={(event) => updateNotes(event.target.value)}
        disabled={!notebook}
      />
    </section>
  );
}

function Notebook() {
  const [selectedNotebook, setSelectedNotebook] = useState(null);
  const [mobilePanel, setMobilePanel] = useState('chat');
  const [activeStudyArtifact, setActiveStudyArtifact] = useState(null);
  const [quickGenerating, setQuickGenerating] = useState('');
  const [quickActionError, setQuickActionError] = useState('');
  const [studioRefreshToken, setStudioRefreshToken] = useState(0);

  const selectNotebook = useCallback((notebook) => {
    setSelectedNotebook(notebook);
    setActiveStudyArtifact(null);
  }, []);

  const openStudyArtifact = useCallback((artifact) => {
    setActiveStudyArtifact(artifact);
    setMobilePanel('chat');
  }, []);

  async function generateQuickArtifact(type) {
    if (!selectedNotebook || quickGenerating) return;
    setQuickGenerating(type);
    setQuickActionError('');
    try {
      const artifact = await generateStudioArtifact(getToken(), selectedNotebook.id, type);
      setStudioRefreshToken((current) => current + 1);
      openStudyArtifact(artifact);
    } catch (error) {
      setQuickActionError(error.message || `Could not generate ${type}.`);
    } finally {
      setQuickGenerating('');
    }
  }

  return (
    <>
      <Navbar />

      <main className="notebook-workspace">
        <nav className="notebook-panel-switcher" aria-label="Notebook panels">
          {[
            ['sources', 'Sources'],
            ['chat', 'Chat'],
          ].map(([panel, label]) => (
            <button
              key={panel}
              type="button"
              className={mobilePanel === panel ? 'active' : ''}
              aria-current={mobilePanel === panel ? 'page' : undefined}
              onClick={() => setMobilePanel(panel)}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className={`notebook-grid notebook-panel-${mobilePanel}`}>
          <div className="notebook-sources border-end">
            <Sidebar
              selectedNotebook={selectedNotebook}
              onNotebookSelect={selectNotebook}
            />
          </div>

          <div className="notebook-chat border-end">
            <div className="notebook-chat-body">
              <div className="notebook-quick-actions" aria-label="Study shortcuts">
                <button type="button" className="btn btn-sm btn-outline-dark" disabled={!selectedNotebook || Boolean(quickGenerating)} onClick={() => void generateQuickArtifact('summary')}>
                  {quickGenerating === 'summary' ? 'Generating summary…' : 'Summary'}
                </button>
                <button type="button" className="btn btn-sm btn-outline-dark" disabled={!selectedNotebook || Boolean(quickGenerating)} onClick={() => void generateQuickArtifact('quiz')}>
                  {quickGenerating === 'quiz' ? 'Generating quiz…' : 'Quiz'}
                </button>
                {quickActionError && <span className="small text-danger" role="alert">{quickActionError}</span>}
              </div>
              <div className="notebook-chat-main">
                <TutorChat
                  notebook={selectedNotebook}
                  studyArtifact={activeStudyArtifact}
                  onCloseStudyArtifact={() => setActiveStudyArtifact(null)}
                />
              </div>
              <LearningStudio
                notebook={selectedNotebook}
                onOpenArtifact={openStudyArtifact}
                refreshToken={studioRefreshToken}
              />
            </div>
          </div>

        </div>

        <div className="notebook-below-chat">
          <NotebookNotes key={selectedNotebook?.id || 'no-notebook'} notebook={selectedNotebook} />
        </div>

        <section className="notebook-extras" aria-label="Additional learning tools">
          <div className="notebook-extra-card notebook-extra-image">
            <ImageAnalyzer notebook={selectedNotebook} />
          </div>
          <div className="notebook-extra-card notebook-extra-speech">
            <SpeechStudio />
          </div>
          <div className="notebook-extra-card notebook-extra-nearby">
            <NearbyResources />
          </div>
        </section>
      </main>
    </>
  );
}

export default Notebook;

// FILE PURPOSE:
// Provides the authenticated notebook workspace with source management,
// mobile panel navigation, tutor chat, Learning Studio, image, and study tools.
