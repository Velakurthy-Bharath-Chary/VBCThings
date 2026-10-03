import { useEffect, useRef, useState } from 'react';

import { analyzeSpeech, deleteSpeechAssessment, listSpeechAssessments } from '../services/api';
import { getToken } from '../services/auth';

function SpeechStudio() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [referenceText, setReferenceText] = useState('');
  const [history, setHistory] = useState([]);
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const recordingChunksRef = useRef([]);

  useEffect(() => {
    let active = true;
    listSpeechAssessments(getToken())
      .then((items) => { if (active) setHistory(items); })
      .catch(() => { if (active) setHistory([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  async function startRecording() {
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Audio recording is not supported in this browser. You can upload an audio file instead.');
      return;
    }
    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
        .find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recordingChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordingChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        setError('The browser could not record this answer. Try uploading an audio file.');
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.onstop = () => {
        const blob = new Blob(recordingChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        const contentType = blob.type.includes('mp4') ? 'audio/mp4' : 'audio/webm';
        const extension = contentType === 'audio/mp4' ? 'mp4' : 'webm';
        if (blob.size > 25 * 1024 * 1024) {
          setError('The recording exceeds the 25 MB audio limit. Record a shorter answer.');
        } else if (blob.size > 0) {
          setFile(new File([blob], `speech-recording.${extension}`, { type: contentType }));
          setResult(null);
        }
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        setRecording(false);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setFile(null);
      setResult(null);
      setRecording(true);
    } catch (err) {
      stream?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      setError(err.name === 'NotAllowedError'
        ? 'Microphone access was declined. You can upload an audio file instead.'
        : 'The microphone could not be opened. Check your device or upload an audio file.');
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!file || loading || recording) return;

    setLoading(true);
    setError('');
    setResult(null);
    try {
      const assessment = await analyzeSpeech(getToken(), file, referenceText);
      setResult(assessment);
      setHistory((current) => [
        {
          id: assessment.assessment_id,
          filename: assessment.filename,
          transcript: assessment.transcript,
          reference_text: referenceText.trim() || null,
          semantic_analysis: assessment.semantic_analysis,
          tone_analysis: assessment.tone_analysis,
          created_at: assessment.created_at,
        },
        ...current,
      ].slice(0, 30));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function removeAssessment(assessmentId) {
    try {
      await deleteSpeechAssessment(getToken(), assessmentId);
      setHistory((items) => items.filter((item) => item.id !== assessmentId));
      if (result?.assessment_id === assessmentId) setResult(null);
    } catch (err) {
      setError(err.message);
    }
  }

  const signals = result?.semantic_analysis?.language_signals;
  const cefr = result?.semantic_analysis?.cefr_estimate;
  const feedback = result?.semantic_analysis?.personalized_feedback;

  return (
    <section className="border-top mt-4 pt-3">
      <h2 className="h6 fw-bold mb-1">Speech &amp; communication</h2>
      <p className="small text-muted mb-3">Transcribe a spoken answer and review language signals.</p>

      <form onSubmit={handleSubmit} className="d-grid gap-2">
        <label htmlFor="speech-upload" className="small fw-semibold">Audio file</label>
        <input
          id="speech-upload"
          type="file"
          className="form-control form-control-sm"
          accept=".wav,.mp3,.mpeg,.mp4,.m4a,.webm"
          disabled={loading || recording}
          onChange={(event) => {
            setFile(event.target.files?.[0] || null);
            setResult(null);
            setError('');
          }}
        />
        <div className="d-flex align-items-center gap-2 flex-wrap">
          {recording ? (
            <button type="button" className="btn btn-outline-danger btn-sm" onClick={stopRecording}>
              Stop recording
            </button>
          ) : (
            <button type="button" className="btn btn-outline-secondary btn-sm" disabled={loading} onClick={() => void startRecording()}>
              Record answer
            </button>
          )}
          {recording && <span className="small text-danger">Recording — select Stop when finished.</span>}
          {file && !recording && <span className="small text-muted">Ready: {file.name}</span>}
        </div>
        <p className="small text-muted mb-1">Recording asks for microphone access and is sent for transcription only when you submit it. Audio is not retained after processing.</p>
        <label htmlFor="speech-reference" className="small fw-semibold">Expected answer or key concepts (optional)</label>
        <textarea
          id="speech-reference"
          className="form-control form-control-sm"
          rows={3}
          maxLength={20000}
          value={referenceText}
          onChange={(event) => setReferenceText(event.target.value)}
          placeholder="Compare your spoken response with an answer or the concepts you wanted to cover."
        />
        <button type="submit" className="btn btn-outline-dark btn-sm" disabled={!file || loading || recording}>
          {loading ? 'Transcribing and analyzing…' : 'Analyze speech'}
        </button>
      </form>

      {error && <div className="alert alert-danger small py-2 mt-3">{error}</div>}

      {result && (
        result.semantic_analysis?.no_speech_detected ? (
          <div className="alert alert-warning small py-3 mt-3">
            <strong>🎙️ No clear speech detected</strong>
            <div className="mt-1">{result.semantic_analysis.message || 'No clear speech was detected in your recording.'}</div>
            <div className="mt-2 text-muted">Please ensure your microphone is enabled and speak clearly into your device, or upload an audio file containing spoken words.</div>
          </div>
        ) : (
          <div className="mt-3">
            <div className="small fw-semibold mb-1">Transcript</div>
            <p className="small border rounded-2 bg-light p-2" style={{ whiteSpace: 'pre-wrap' }}>
              {result.transcript || 'No speech was detected.'}
            </p>
            <div className="row g-2 mb-2">
              <div className="col-6">
                <div className="border rounded-2 p-2 h-100">
                  <div className="small text-muted">CEFR-oriented estimate</div>
                  <div className="fw-bold">{cefr?.level || (cefr?.sample_sufficient === false ? 'More speech needed' : '—')}</div>
                  <div className="small text-muted">{cefr?.basis}</div>
                </div>
              </div>
              <div className="col-6">
                <div className="border rounded-2 p-2 h-100">
                  <div className="small text-muted">Word-based tone</div>
                  <div className="fw-bold text-capitalize">{result.tone_analysis?.sentiment || '—'}</div>
                  <div className="small text-muted">not an assessment of emotional state</div>
                </div>
              </div>
            </div>
            {result.semantic_analysis?.answer_relevance && (
              <div className="alert alert-info small py-2">
                <strong>Meaning match: {Math.round(result.semantic_analysis.answer_relevance.similarity * 100)}%</strong>
                <div>{result.semantic_analysis.answer_relevance.interpretation}</div>
                <div className="text-muted">{result.semantic_analysis.answer_relevance.basis}</div>
              </div>
            )}
            {result.semantic_analysis?.answer_assessment && (
              result.semantic_analysis.answer_assessment.status === 'unavailable' ? (
                <div className="alert alert-warning small py-2">
                  {result.semantic_analysis.answer_assessment.message}
                </div>
              ) : (
                <div className="border rounded-2 p-2 mb-2">
                  <div className="small fw-semibold mb-1">
                    Reference-based answer review: {result.semantic_analysis.answer_assessment.classification}
                  </div>
                  <p className="small mb-2">{result.semantic_analysis.answer_assessment.reasoning}</p>
                  {result.semantic_analysis.answer_assessment.evidence_quotes?.length > 0 && (
                    <div className="small mb-2">
                      <span className="fw-semibold">Transcript evidence</span>
                      <ul className="mb-1">
                        {result.semantic_analysis.answer_assessment.evidence_quotes.map((quote) => (
                          <li key={quote}><q>{quote}</q></li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.semantic_analysis.answer_assessment.covered_concepts?.length > 0 && (
                    <div className="small mb-1"><strong>Covered:</strong> {result.semantic_analysis.answer_assessment.covered_concepts.join(' · ')}</div>
                  )}
                  {result.semantic_analysis.answer_assessment.missing_concepts?.length > 0 && (
                    <div className="small mb-1"><strong>Review:</strong> {result.semantic_analysis.answer_assessment.missing_concepts.join(' · ')}</div>
                  )}
                  {result.semantic_analysis.answer_assessment.possible_misconceptions?.length > 0 && (
                    <div className="small mb-1"><strong>Possible conflicts with the reference:</strong> {result.semantic_analysis.answer_assessment.possible_misconceptions.join(' · ')}</div>
                  )}
                  <div className="small text-muted">This is model-assisted feedback based only on the reference you supplied; check it against your course material.</div>
                </div>
              )
            )}
            {feedback && (
              <div className="border rounded-2 p-2 mb-2">
                <div className="small fw-semibold mb-1">Your practice feedback</div>
                {feedback.strengths?.length > 0 && (
                  <>
                    <div className="small fw-semibold">What is working</div>
                    <ul className="small mb-2">
                      {feedback.strengths.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </>
                )}
                {feedback.next_steps?.length > 0 && (
                  <>
                    <div className="small fw-semibold">Try next</div>
                    <ul className="small mb-1">
                      {feedback.next_steps.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </>
                )}
                <div className="small text-muted">{feedback.basis}</div>
              </div>
            )}
            {signals && (
              <p className="small text-muted mb-2">
                {signals.word_count} words · {signals.sentence_count} sentences · average sentence length {signals.average_sentence_length}
              </p>
            )}
            <p className="small text-muted mb-0">
              This heuristic estimate is not a certified CEFR assessment. It evaluates transcript text, not pronunciation or acoustic quality.
            </p>
          </div>
        )
      )}
      {history.length > 0 && (
        <div className="mt-3">
          <h3 className="small fw-semibold">Recent assessments</h3>
          <ul className="list-unstyled d-grid gap-2">
            {history.map((item) => (
              <li key={item.id} className="border rounded-2 p-2 d-flex justify-content-between align-items-center gap-2">
                <button
                  type="button"
                  className="btn btn-link btn-sm text-start p-0 text-decoration-none"
                  onClick={() => setResult({
                    assessment_id: item.id,
                    filename: item.filename,
                    transcript: item.transcript,
                    semantic_analysis: item.semantic_analysis,
                    tone_analysis: item.tone_analysis,
                  })}
                >
                  <span className="d-block fw-semibold">{item.filename}</span>
                  <span className="small text-muted">{new Date(item.created_at).toLocaleString()}</span>
                </button>
                <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => void removeAssessment(item.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default SpeechStudio;

// FILE PURPOSE:
// Provides authenticated audio upload and recording, speech analysis results,
// reference-based answer review, and owner-scoped assessment history.
