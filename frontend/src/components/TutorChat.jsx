import { useEffect, useRef, useState } from 'react';

import {
  createChat,
  createChatMessage,
  deleteChat,
  getChatMessages,
  getQuizAttempts,
  getChats,
  renameChat,
  runOrchestratorStream,
  submitQuizAttempt,
  updateChat,
} from '../services/api';

import { getToken } from '../services/auth';
import MarkdownContent from './MarkdownContent';

function restoreMessage(row) {
  if (row.role !== 'assistant') return { role: row.role, content: row.content };
  const rawContent = String(row.content || '');
  try {
    let parsed = JSON.parse(rawContent);
    if (typeof parsed === 'string') parsed = JSON.parse(parsed);
    if (parsed?.kind === 'assistant-message-v1' && parsed.message && typeof parsed.message === 'object') {
      return {
        ...parsed.message,
        role: 'assistant',
        content: String(parsed.message.content ?? parsed.content ?? ''),
        message_id: row.id,
      };
    }
  } catch {
    // Legacy plain-text assistant messages remain readable.
  }
  return { role: 'assistant', content: rawContent, sources: [], message_id: row.id };
}

function serializeAssistant(message) {
  return JSON.stringify({ kind: 'assistant-message-v1', message });
}

function StudyArtifactView({ artifact, onClose }) {
  const [revealed, setRevealed] = useState(false);
  const [cardIndex, setCardIndex] = useState(0);
  const [quizAnswers, setQuizAnswers] = useState({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const cards = artifact.artifact_type === 'flashcards'
    ? [...artifact.content.matchAll(/(?:^|\n)Q:\s*([\s\S]*?)\nA:\s*([\s\S]*?)(?=\nQ:\s*|$)/gim)]
      .map((match) => ({ question: match[1].trim(), answer: match[2].trim() }))
    : [];
  const activeCard = cards[cardIndex];
  let quiz = null;
  if (artifact.artifact_type === 'quiz') {
    try {
      const jsonContent = artifact.content.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
      const parsed = JSON.parse(jsonContent);
      if (Array.isArray(parsed.questions) && parsed.questions.length) quiz = parsed;
    } catch {
      // Older saved quizzes remain readable as text.
    }
  }

  function handleQuizSubmit(event) {
    event.preventDefault();
    if (!quiz || quiz.questions.some((_, index) => !quizAnswers[index])) return;
    setQuizSubmitted(true);
  }

  return (
    <section className="study-artifact-view h-100 d-flex flex-column" aria-label={artifact.title}>
      <header className="d-flex justify-content-between align-items-center gap-3 mb-4">
        <div>
          <div className="small text-muted">Learning Studio · {artifact.artifact_type.replace('_', ' ')}</div>
          <h3 className="h4 fw-bold mb-0">{artifact.title}</h3>
        </div>
        <button type="button" className="btn btn-outline-dark" onClick={onClose}>Back to chat</button>
      </header>

      {activeCard ? (
        <div className="study-flashcard-stage flex-grow-1 d-flex flex-column align-items-center justify-content-center">
          <div className="small text-muted mb-3">Card {cardIndex + 1} of {cards.length}</div>
          <article className="study-flashcard card shadow-sm w-100" aria-live="polite">
            <div className="card-body d-flex flex-column justify-content-center p-4 p-lg-5">
              <div className="text-uppercase small text-muted fw-semibold mb-3">{revealed ? 'Answer' : 'Question'}</div>
              <div className="study-flashcard-text">{revealed ? activeCard.answer : activeCard.question}</div>
            </div>
          </article>
          <div className="d-flex align-items-center gap-2 mt-4">
            <button type="button" className="btn btn-outline-secondary" disabled={cardIndex === 0} onClick={() => { setCardIndex((value) => value - 1); setRevealed(false); }}>Previous</button>
            <button type="button" className="btn btn-dark" onClick={() => setRevealed((value) => !value)}>{revealed ? 'Show question' : 'Reveal answer'}</button>
            <button type="button" className="btn btn-outline-secondary" disabled={cardIndex === cards.length - 1} onClick={() => { setCardIndex((value) => value + 1); setRevealed(false); }}>Next</button>
          </div>
        </div>
      ) : quiz ? (
        <form className="study-artifact-content flex-grow-1 overflow-auto border rounded-3 bg-white p-4 p-lg-5" onSubmit={handleQuizSubmit}>
          <p className="text-muted mb-4">Choose one answer for each question, then submit to see your score.</p>
          {quiz.questions.map((item, index) => {
            const options = Array.isArray(item.options)
              ? item.options.map((text, optionIndex) => [String.fromCharCode(65 + optionIndex), text])
              : Object.entries(item.options || {});
            return (
              <fieldset key={`${index}-${item.question}`} className="border rounded-3 p-3 p-lg-4 mb-3">
                <legend className="fs-6 fw-semibold">{index + 1}. {item.question}</legend>
                {options.map(([key, text]) => (
                  <label key={key} className={`study-quiz-option${quizSubmitted && key === item.correct_answer ? ' is-correct' : ''}${quizSubmitted && quizAnswers[index] === key && key !== item.correct_answer ? ' is-incorrect' : ''}`}>
                    <input type="radio" name={`study-quiz-${artifact.id}-${index}`} checked={quizAnswers[index] === key} disabled={quizSubmitted} onChange={() => setQuizAnswers((current) => ({ ...current, [index]: key }))} />
                    <span><strong>{key}.</strong> {text}</span>
                  </label>
                ))}
                {quizSubmitted && item.explanation && <p className="small text-muted mt-2 mb-0">{item.explanation}</p>}
              </fieldset>
            );
          })}
          {quizSubmitted ? (
            <div className="alert alert-success mb-0">Score: {quiz.questions.reduce((score, item, index) => score + (quizAnswers[index] === item.correct_answer ? 1 : 0), 0)} / {quiz.questions.length}</div>
          ) : (
            <button className="btn btn-dark" type="submit" disabled={quiz.questions.some((_, index) => !quizAnswers[index])}>Submit quiz</button>
          )}
        </form>
      ) : (
        <div className="study-artifact-content flex-grow-1 overflow-auto border rounded-3 bg-white p-4 p-lg-5">
          <MarkdownContent content={artifact.content} className="study-artifact-prose-content" />
        </div>
      )}
    </section>
  );
}

function TutorChat({ notebook, studyArtifact, onCloseStudyArtifact }) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [quizAnswers, setQuizAnswers] = useState({});
  const [submittedQuizzes, setSubmittedQuizzes] = useState({});
  const [submittingQuizId, setSubmittingQuizId] = useState(null);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [loadedChatId, setLoadedChatId] = useState(null);
  const [chatsNotebookId, setChatsNotebookId] = useState(null);
  const [showArchived, setShowArchived] = useState(false);
  const activeRequestRef = useRef(null);
  const notebookId = notebook?.id;

  useEffect(() => {
    if (!notebookId) return undefined;
    let active = true;
    const token = getToken();
    getChats(token, notebookId, showArchived)
      .then(async (existingChats) => {
        let availableChats = existingChats;
        if (availableChats.length === 0) {
          availableChats = [await createChat(token, notebookId)];
        }
        if (!active) return;
        setChats(availableChats);
        setChatsNotebookId(notebookId);
        setActiveChatId((previousId) => (
          availableChats.some((chat) => chat.id === previousId)
            ? previousId
            : availableChats[0]?.id || null
        ));
      })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [notebookId, showArchived]);

  useEffect(() => {
    if (!activeChatId || chatsNotebookId !== notebook?.id) return undefined;
    let active = true;
    Promise.all([
      getChatMessages(getToken(), activeChatId),
      getQuizAttempts(getToken(), notebook.id),
    ])
      .then(([rows, attempts]) => {
        if (!active) return;
        const restored = rows.map(restoreMessage);
        const attemptsByMessage = Object.fromEntries(attempts.map((attempt) => [attempt.message_id, attempt]));
        const restoredAnswers = {};
        restored.forEach((message) => {
          const attempt = attemptsByMessage[message.message_id];
          attempt?.answers.forEach((answer, questionIndex) => {
            restoredAnswers[`${message.message_id}-${questionIndex}`] = answer;
          });
        });
        setMessages(restored);
        setLoadedChatId(activeChatId);
        setQuizAnswers(restoredAnswers);
        setSubmittedQuizzes(attemptsByMessage);
      })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [activeChatId, chatsNotebookId, notebook?.id]);

  const activeChat = chats.find((chat) => chat.id === activeChatId);
  const chatIsReady = Boolean(activeChat && loadedChatId === activeChatId && chatsNotebookId === notebook?.id);
  const isLoadingChats = Boolean(notebook && chatsNotebookId !== notebook.id);
  const visibleMessages = chatIsReady ? messages : [];
  const isLoadingMessages = Boolean(activeChatId && chatIsReady === false && !isLoadingChats);

  async function handleNewChat() {
    if (!notebook) return;
    try {
      const chat = await createChat(getToken(), notebook.id);
      setChats((current) => [chat, ...current]);
      setChatsNotebookId(notebook.id);
      setActiveChatId(chat.id);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRenameChat() {
    if (!activeChat) return;
    const title = window.prompt('Conversation name:', activeChat.title);
    if (!title?.trim()) return;
    try {
      const updated = await renameChat(getToken(), activeChat.id, title.trim());
      setChats((current) => current.map((chat) => chat.id === updated.id ? updated : chat));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteChat() {
    if (!activeChat) return;
    try {
      await deleteChat(getToken(), activeChat.id);
      const remaining = chats.filter((chat) => chat.id !== activeChat.id);
      if (remaining.length === 0) {
        const replacement = await createChat(getToken(), notebook.id);
        remaining.push(replacement);
      }
      setChats(remaining);
      setActiveChatId(remaining[0]?.id || null);
      setLoadedChatId(null);
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleChatFlag(field) {
    if (!activeChat) return;
    const updated = await updateChat(getToken(), activeChat.id, {
      [field]: !activeChat[field],
    });
    if (field === 'is_archived' && updated.is_archived && !showArchived) {
      const remaining = chats.filter((chat) => chat.id !== updated.id);
      setChats(remaining);
      setActiveChatId(remaining[0]?.id || null);
      setLoadedChatId(null);
      return;
    }
    setChats((current) => current
      .map((chat) => chat.id === updated.id ? updated : chat)
      .sort((left, right) => Number(right.is_pinned) - Number(left.is_pinned)));
  }

  async function persistAssistantMessage(chatId, message) {
    return createChatMessage(
      getToken(),
      chatId,
      'assistant',
      serializeAssistant({ role: 'assistant', ...message }),
    );
  }

  async function submitQuiz(message) {
    if (!activeChatId || !message.message_id || submittingQuizId) return;
    const answers = message.quiz.questions.map((_, questionIndex) => (
      quizAnswers[`${message.message_id}-${questionIndex}`]
    ));
    if (answers.some((answer) => !answer)) return;
    setSubmittingQuizId(message.message_id);
    setError('');
    try {
      const attempt = await submitQuizAttempt(
        getToken(), activeChatId, message.message_id, answers,
      );
      setSubmittedQuizzes((current) => ({ ...current, [message.message_id]: attempt }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmittingQuizId(null);
    }
  }

  useEffect(() => {
    async function handleImageAnalysis(event) {
      const result = event.detail;

      if (
        !result ||
        result.notebook_id !== notebook?.id
      ) {
        return;
      }

      setMessages((current) => [
        ...current,
        {
          role: 'user',
          content: `🖼️ Image: ${result.question}`,
        },
        {
          role: 'assistant',
          content: result.answer,
          sources: [],
          agent: 'image',
        },
      ]);
      if (activeChatId && chatsNotebookId === notebook.id) {
        try {
          await createChatMessage(
            getToken(), activeChatId, 'user', `Image: ${result.question}`,
          );
          await persistAssistantMessage(activeChatId, {
            content: result.answer,
            sources: [],
            agent: 'image',
          });
        } catch (err) {
          setError(err.message);
        }
      }
    }

    window.addEventListener(
      'image-analysis-complete',
      handleImageAnalysis,
    );

    return () => {
      window.removeEventListener(
        'image-analysis-complete',
        handleImageAnalysis,
      );
    };
  }, [activeChatId, chatsNotebookId, notebook?.id]);

  function handleSubmit(event) {
    event.preventDefault();
    void sendQuestion(question);
  }

  async function sendQuestion(requestText, appendUser = true) {
    const trimmedQuestion = requestText.trim();

    if (!notebook || !chatIsReady || !trimmedQuestion || loading) {
      return;
    }

    setError('');
    setQuestion('');
    setLoading(true);
    const abortController = new AbortController();
    activeRequestRef.current = abortController;

    const userMessage = {
      role: 'user',
      content: trimmedQuestion,
    };

    const assistantMessage = {
      role: 'assistant',
      content: '',
      sources: [],
      agent: 'tutor',
      resources: [],
    };
    let activeAgent = 'tutor';

    setMessages((current) => appendUser
      ? [...current, userMessage, assistantMessage]
      : [...current, assistantMessage]);

    const chatId = activeChat.id;
    let streamedContent = '';
    let streamedSources = [];
    try {
      const token = getToken();
      if (appendUser) {
        await createChatMessage(token, chatId, 'user', trimmedQuestion);
      }

      /*
       * The orchestrator decides whether the request
       * should go to the tutor, quiz, resource, image,
       * or another agent.
       */
      const result = await runOrchestratorStream(
        token,
        notebook.id,
        trimmedQuestion,
        3,
         (agent) => {
           activeAgent = agent;
           setMessages((current) => {
             const updated = [...current];
             updated[updated.length - 1] = { ...updated.at(-1), agent };
             return updated;
           });
         },
        (chunk) => setMessages((current) => {
          streamedContent += chunk;
          const updated = [...current];
          const last = updated.length - 1;
          updated[last] = { ...updated[last], content: updated[last].content + chunk };
          return updated;
        }),
        (sources) => {
          streamedSources = sources;
          setMessages((current) => {
            const updated = [...current];
            updated[updated.length - 1] = { ...updated.at(-1), sources };
            return updated;
          });
        },
        activeChat.id,
        abortController.signal,
      );

      /*
       * RESOURCE AGENT
       *
       * Current/latest/web-search requests are handled
       * by the Resource Agent.
       */
      if (result?.agent === 'resource') {
        const resources = result.results || [];

        setMessages((current) => {
          const updated = [...current];
          const lastIndex = updated.length - 1;

          updated[lastIndex] = {
            ...updated[lastIndex],
            agent: 'resource',
            content:
              resources.length > 0
                ? 'I found these resources for your question:'
                : 'I could not find any resources for this question.',
            resources,
          };

          return updated;
        });
        await persistAssistantMessage(chatId, {
          agent: 'resource',
          content: resources.length > 0
            ? 'I found these resources for your question:'
            : 'I could not find any resources for this question.',
          resources,
          sources: [],
        });

        return;
      }

      /*
       * QUIZ AGENT
       *
       * Keep the quiz response visible in the tutor
       * conversation for now. Learning Studio can later
       * consume the same structured quiz object.
       */
      if (result?.agent === 'quiz') {
        setMessages((current) => {
          const updated = [...current];
          const lastIndex = updated.length - 1;

          updated[lastIndex] = {
            ...updated[lastIndex],
            agent: 'quiz',
            content: result.message || 'Select one answer for each question, then submit.',
            quiz: result.quiz,
            sources: result.sources || [],
          };

          return updated;
        });
        const savedQuiz = await persistAssistantMessage(chatId, {
          agent: 'quiz',
          content: result.message || 'Select one answer for each question, then submit.',
          quiz: result.quiz,
          sources: result.sources || [],
        });
        setMessages((current) => current.map((item, messageIndex) => (
          messageIndex === current.length - 1
            ? { ...item, message_id: savedQuiz.id }
            : item
        )));

        return;
      }

      // Tutor answers arrive as streamed chunks and sources; the stream does
      // not emit a final `result` event, so use the routed agent here.
      if (activeAgent === 'tutor' || result?.agent === 'tutor') {
        await persistAssistantMessage(chatId, {
          agent: 'tutor',
          content: streamedContent,
          sources: streamedSources,
        });
        return;
      }
      if (!result) return;

      /*
       * Generic fallback.
       *
       * This prevents the UI from becoming blank if
       * another backend agent is added later.
       */
      setMessages((current) => {
        const updated = [...current];
        const lastIndex = updated.length - 1;

        updated[lastIndex] = {
          ...updated[lastIndex],
          agent: result.agent || 'assistant',
          content:
            result.answer ||
            result.content ||
            'The request was processed.',
        };

        return updated;
      });
      await persistAssistantMessage(chatId, {
        agent: result.agent || 'assistant',
        content: result.answer || result.content || 'The request was processed.',
        sources: result.sources || [],
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        const stoppedMessage = streamedContent
          ? `${streamedContent}\n\n(Response stopped.)`
          : 'Response stopped.';
        setMessages((current) => {
          const updated = [...current];
          const lastIndex = updated.length - 1;
          updated[lastIndex] = {
            ...updated[lastIndex],
            agent: activeAgent,
            content: stoppedMessage,
            sources: streamedSources,
          };
          return updated;
        });
        await persistAssistantMessage(chatId, {
          agent: activeAgent,
          content: stoppedMessage,
          sources: streamedSources,
        }).catch(() => {});
        return;
      }
      const errorContent = streamedContent
        ? `${streamedContent}\n\nI couldn't finish the response: ${err.message}`
        : (err.message || 'Sorry, I could not generate an answer.');
      setError(err.message || 'The response could not be completed.');

      setMessages((current) => {
        const updated = [...current];
        const lastIndex = updated.length - 1;

        updated[lastIndex] = {
          ...updated[lastIndex],
          agent: activeAgent,
          content: errorContent,
          sources: streamedSources,
        };

        return updated;
      });
      await persistAssistantMessage(chatId, {
        agent: activeAgent,
        content: errorContent,
        sources: streamedSources,
      }).catch(() => {});
    } finally {
      if (activeRequestRef.current === abortController) activeRequestRef.current = null;
      setLoading(false);
    }
  }

  function stopResponse() {
    activeRequestRef.current?.abort();
  }

  function handleRegenerate(messageIndex) {
    const previousQuestion = visibleMessages
      .slice(0, messageIndex)
      .reverse()
      .find((message) => message.role === 'user')?.content;
    if (previousQuestion) void sendQuestion(previousQuestion, false);
  }

  async function handleCopy(content) {
    try {
      await navigator.clipboard.writeText(content);
      setError('');
    } catch {
      setError('Could not copy this response.');
    }
  }

  return (
    <section className={`d-flex flex-column h-100 p-3 p-lg-4${studyArtifact ? ' tutor-study-mode' : ''}`}>
      {studyArtifact ? (
        <StudyArtifactView key={studyArtifact.id} artifact={studyArtifact} onClose={onCloseStudyArtifact} />
      ) : <>
      <div className="mb-3">
        <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
          <h2 className="h5 fw-bold mb-0">Tutor</h2>
          <div className="d-flex align-items-center gap-1">
            <label className="visually-hidden" htmlFor="chat-select">Conversation</label>
            <select
              id="chat-select"
              className="form-select form-select-sm"
              value={activeChatId || ''}
              disabled={isLoadingChats || chats.length === 0 || loading}
              onChange={(event) => setActiveChatId(Number(event.target.value))}
              aria-label="Choose conversation"
            >
              {chats.map((chat) => <option key={chat.id} value={chat.id}>{chat.title}</option>)}
            </select>
            <button type="button" className="btn btn-outline-dark btn-sm" onClick={handleNewChat} disabled={!notebook || isLoadingChats || loading} aria-label="New conversation">+</button>
            <button type="button" className="btn btn-outline-secondary btn-sm" onClick={handleRenameChat} disabled={!activeChat || loading} aria-label="Rename conversation">Rename</button>
            <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => toggleChatFlag('is_pinned').catch((err) => setError(err.message))} disabled={!activeChat || loading}>{activeChat?.is_pinned ? 'Unpin' : 'Pin'}</button>
            <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => toggleChatFlag('is_archived').catch((err) => setError(err.message))} disabled={!activeChat || loading}>{activeChat?.is_archived ? 'Restore' : 'Archive'}</button>
            <button type="button" className="btn btn-outline-danger btn-sm" onClick={handleDeleteChat} disabled={!activeChat || loading} aria-label="Delete conversation">Delete</button>
          </div>
        </div>
        <label className="small d-flex align-items-center gap-2 mb-2">
          <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />
          Show archived conversations
        </label>

        <p className="text-muted small mb-0">
          {notebook
            ? `Ask questions about ${notebook.name}.`
            : 'Select a notebook to start learning.'}
        </p>
      </div>

      <div className="flex-grow-1 overflow-auto border rounded-3 bg-light p-3">
        {!notebook ? (
          <div className="h-100 d-flex align-items-center justify-content-center">
            <div className="text-center text-muted">
              <div className="fs-1 mb-2">
                📚
              </div>

              <p className="mb-0">
                Select a notebook from the Sources panel.
              </p>
            </div>
          </div>
        ) : isLoadingChats || isLoadingMessages ? (
          <div className="h-100 d-flex align-items-center justify-content-center">
            <span className="spinner-border spinner-border-sm" role="status"><span className="visually-hidden">Loading conversation</span></span>
          </div>
        ) : visibleMessages.length === 0 ? (
          <div className="h-100 d-flex align-items-center justify-content-center">
            <div className="text-center text-muted">
              <div className="fs-1 mb-2">
                💬
              </div>

              <p className="mb-1">
                Ask your first question.
              </p>

              <small>
                I'll answer using your uploaded sources.
              </small>
            </div>
          </div>
        ) : (
          <div className="d-flex flex-column gap-3">
            {visibleMessages.map((message, index) => (
              <div
                key={index}
                className={
                  message.role === 'user'
                    ? 'd-flex justify-content-end'
                    : 'd-flex justify-content-start'
                }
              >
                <div
                  className={
                    message.role === 'user'
                      ? 'bg-dark text-white rounded-3 px-3 py-2'
                      : 'bg-white border rounded-3 px-3 py-2'
                  }
                  style={{ maxWidth: '90%' }}
                >
                  {message.role === 'assistant' ? (
                    <MarkdownContent content={message.content} />
                  ) : (
                    <div className="small user-message-content" style={{ whiteSpace: 'pre-wrap' }}>
                      {message.content}
                    </div>
                  )}

                  {message.quiz?.questions?.length > 0 && (
                    <div className="mt-3">
                      <h3 className="h6 fw-bold">Practice Quiz</h3>
                      {message.quiz.questions.map((item, questionIndex) => {
                        const answerKey = `${message.message_id}-${questionIndex}`;
                        const selected = quizAnswers[answerKey];
                        const submitted = submittedQuizzes[message.message_id];
                        return (
                          <fieldset key={questionIndex} className="border rounded-2 p-2 mb-2">
                            <legend className="small fw-semibold mb-2">
                              {questionIndex + 1}. {item.question}
                            </legend>
                            {Object.entries(item.options || {}).map(([optionKey, optionText]) => (
                              <label key={optionKey} className="d-flex gap-2 align-items-start small mb-1">
                                <input
                                  type="radio"
                                  name={`quiz-${answerKey}`}
                                  value={optionKey}
                                  checked={selected === optionKey}
                                  disabled={submitted}
                                  onChange={() => setQuizAnswers((current) => ({ ...current, [answerKey]: optionKey }))}
                                />
                                <span>{optionKey}. {optionText}</span>
                              </label>
                            ))}
                            {submitted && (
                              <div className="small mt-2">
                                <strong>{selected === item.correct_answer ? 'Correct' : `Correct answer: ${item.correct_answer}`}</strong>
                                {item.explanation && <div className="text-muted">{item.explanation}</div>}
                              </div>
                            )}
                          </fieldset>
                        );
                      })}
                      {submittedQuizzes[message.message_id] ? (
                        <div className="alert alert-success py-2 small mb-0">
                          Score: {submittedQuizzes[message.message_id].score} / {submittedQuizzes[message.message_id].total_questions}
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          disabled={!message.message_id || submittingQuizId === message.message_id || message.quiz.questions.some((_, questionIndex) => !quizAnswers[`${message.message_id}-${questionIndex}`])}
                          onClick={() => void submitQuiz(message)}
                        >
                          {submittingQuizId === message.message_id ? 'Scoring…' : 'Submit answers'}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Agent label */}
                  {message.role === 'assistant' &&
                    message.agent && (
                      <div className="mt-2">
                        <span className="badge text-bg-light">
                          {message.agent}
                        </span>
                      </div>
                    )}

                  {message.role === 'assistant' && message.content && (
                    <div className="d-flex gap-2 mt-2">
                      <button type="button" className="btn btn-link btn-sm p-0" onClick={() => void handleCopy(message.content)}>
                        Copy
                      </button>
                      <button type="button" className="btn btn-link btn-sm p-0" disabled={loading || !chatIsReady || message.agent === 'image'} onClick={() => handleRegenerate(index)}>
                        Regenerate
                      </button>
                    </div>
                  )}

                  {/* RAG sources */}
                  {message.role === 'assistant' &&
                    message.sources?.length > 0 && (
                      <div className="border-top mt-3 pt-2">
                        <div className="small fw-semibold mb-1">
                          Sources
                        </div>

                        {message.sources.map(
                          (source, sourceIndex) => (
                            <div
                              key={sourceIndex}
                              className="small text-muted"
                            >
                              {source.source}
                              {' · '}
                              chunk {source.chunk_index}
                            </div>
                          ),
                        )}
                      </div>
                    )}

                  {/* Resource Agent results */}
                  {message.role === 'assistant' &&
                    message.resources?.length > 0 && (
                      <div className="border-top mt-3 pt-3">
                        <div className="small fw-semibold mb-2">
                          Web Resources
                        </div>

                        <div className="d-flex flex-column gap-2">
                          {message.resources.map(
                            (resource, resourceIndex) => (
                              <a
                                key={resourceIndex}
                                href={/^https?:\/\//i.test(resource.url || '') ? resource.url : undefined}
                                target="_blank"
                                rel="noreferrer"
                                className="text-decoration-none border rounded-2 p-2"
                              >
                                <div className="small fw-semibold">
                                  {resource.title ||
                                    'Resource'}
                                </div>

                                {resource.snippet && (
                                  <div className="small text-muted mt-1">
                                    {resource.snippet}
                                  </div>
                                )}

                                <div className="small text-primary mt-1 text-truncate">
                                  {resource.url}
                                </div>
                              </a>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="d-flex justify-content-start">
                <div className="bg-white border rounded-3 px-3 py-2">
                  <div className="d-flex align-items-center gap-2">
                    <div
                      className="spinner-border spinner-border-sm"
                      role="status"
                    />

                    <span className="small text-muted">
                      Thinking...
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-danger small py-2 mt-3 mb-0">
          {error}
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="input-group mt-3"
      >
        <input
          type="text"
          className="form-control"
          placeholder={
            notebook
              ? 'Ask something about your sources...'
              : 'Select a notebook first'
          }
          value={question}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          disabled={!notebook || !chatIsReady || loading}
        />

        {loading ? (
          <button type="button" className="btn btn-outline-danger" onClick={stopResponse}>
            Stop
          </button>
        ) : (
          <button
            type="submit"
            className="btn btn-dark"
            disabled={!notebook || !chatIsReady || !question.trim()}
          >
            Send
          </button>
        )}
      </form>
      </>}
    </section>
  );
}

export default TutorChat;

// FILE PURPOSE:
// Provides the central agentic tutor interface.
// Routes user requests through the orchestrator,
// persists conversations, supports streamed tutoring and quizzes,
// resource-search results, and image-analysis results.
