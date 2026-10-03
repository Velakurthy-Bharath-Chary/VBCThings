const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? '/api' : 'http://localhost:8000');

async function apiRequest(endpoint, options = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.detail || 'Something went wrong.');
  }

  return data;
}

export function registerUser(email, password) {
  return apiRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function loginUser(email, password) {
  return apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export function getCurrentUser(token) {
  return apiRequest('/auth/me', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function askRag(token, notebookId, question, topK = 3) {
  return apiRequest('/rag/ask', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      notebook_id: notebookId,
      question,
      top_k: topK,
    }),
  });
}

export async function askRagStream(
  token,
  notebookId,
  question,
  topK = 3,
  onChunk,
  onSources,
) {
  const response = await fetch(`${API_BASE_URL}/rag/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      notebook_id: notebookId,
      question,
      top_k: topK,
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'Something went wrong.');
  }

  if (!response.body) {
    throw new Error('Streaming is not supported by this browser.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.trim()) continue;

      const event = JSON.parse(line);

      if (event.type === 'chunk') {
        onChunk(event.content);
      } else if (event.type === 'sources') {
        onSources(event.sources);
      }
    }
  }

  buffer += decoder.decode();

  if (buffer.trim()) {
    const event = JSON.parse(buffer);

    if (event.type === 'chunk') {
      onChunk(event.content);
    } else if (event.type === 'sources') {
      onSources(event.sources);
    }
  }
}

export function getNotebooks(token) {
  return apiRequest('/notebooks', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function getChats(token, notebookId, includeArchived = false) {
  return apiRequest(`/chats?notebook_id=${notebookId}&include_archived=${includeArchived}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function createChat(token, notebookId, title = 'New Chat') {
  return apiRequest(`/chats?notebook_id=${notebookId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ title }),
  });
}

export function getChatMessages(token, chatId) {
  return apiRequest(`/chats/${chatId}/messages`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function createChatMessage(token, chatId, role, content) {
  return apiRequest(`/chats/${chatId}/messages`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ role, content }),
  });
}

export function renameChat(token, chatId, title) {
  return updateChat(token, chatId, { title });
}

export function updateChat(token, chatId, updates) {
  return apiRequest(`/chats/${chatId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(updates),
  });
}

export function deleteChat(token, chatId) {
  return fetch(`${API_BASE_URL}/chats/${chatId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  }).then((response) => {
    if (!response.ok) throw new Error('Could not delete this conversation.');
  });
}

export function createNotebook(token, name, description = '') {
  return apiRequest('/notebooks', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name,
      description,
    }),
  });
}

export function getStudioArtifacts(token, notebookId) {
  return apiRequest(`/studio/artifacts?notebook_id=${notebookId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function getStudioProgress(token, notebookId) {
  return apiRequest(`/studio/progress?notebook_id=${notebookId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function generateStudioArtifact(
  token,
  notebookId,
  artifactType,
  title = null,
  instructions = null,
) {
  return apiRequest('/studio/generate', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      notebook_id: notebookId,
      artifact_type: artifactType,
      title,
      instructions,
    }),
  });
}

export function deleteStudioArtifact(token, artifactId) {
  return apiRequest(`/studio/artifacts/${artifactId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function uploadDocument(token, notebookId, file) {
  const formData = new FormData();

  formData.append('notebook_id', notebookId);
  formData.append('file', file);

  return fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  }).then(async (response) => {
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(data?.detail || 'Document upload failed.');
    }

    return data;
  });
}

export function analyzeImage(
  token,
  notebookId,
  file,
  question,
) {
  const formData = new FormData();

  formData.append('notebook_id', notebookId);
  formData.append('file', file);
  formData.append('question', question);

  return fetch(`${API_BASE_URL}/image/analyze`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  }).then(async (response) => {
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(
        data?.detail || 'Image analysis failed.',
      );
    }

    return data;
  });
}

export function getDocuments(token, notebookId) {
  return apiRequest(`/documents?notebook_id=${notebookId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function deleteDocument(token, documentId) {
  return apiRequest(`/documents/${documentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
}


export function runOrchestrator(
  token,
  notebookId,
  question,
  topK = 3,
) {
  return apiRequest('/orchestrator/run', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      notebook_id: notebookId,
      question,
      top_k: topK,
    }),
  });
}

export async function runOrchestratorStream(
  token, notebookId, question, topK = 3,
  onAgent = () => {}, onChunk = () => {}, onSources = () => {}, chatId = null, signal,
) {
  const response = await fetch(`${API_BASE_URL}/orchestrator/run/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ notebook_id: notebookId, chat_id: chatId, question, top_k: topK }),
    signal,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'The request could not be routed.');
  }
  if (!response.body) throw new Error('Streaming is not supported by this browser.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result = null;
  const consume = (line) => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === 'agent') onAgent(event.agent);
    else if (event.type === 'chunk') onChunk(event.content);
    else if (event.type === 'sources') onSources(event.sources);
    else if (event.type === 'result') result = event.result;
    else if (event.type === 'error') {
      if (event.agent) onAgent(event.agent);
      throw new Error(event.message);
    }
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      lines.forEach(consume);
    }
    buffer += decoder.decode();
    if (buffer.trim()) consume(buffer);
    return result;
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
}

export function analyzeImageThroughOrchestrator(token, notebookId, file, question) {
  const formData = new FormData();
  formData.append('notebook_id', notebookId);
  formData.append('file', file);
  formData.append('question', question);
  return fetch(`${API_BASE_URL}/orchestrator/image`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  }).then(async (response) => {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || 'Image analysis failed.');
    return data;
  });
}

export function analyzeSpeech(token, file, referenceText = '') {
  const formData = new FormData();
  formData.append('file', file);
  if (referenceText.trim()) formData.append('reference_text', referenceText.trim());
  return fetch(`${API_BASE_URL}/orchestrator/speech`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  }).then(async (response) => {
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.detail || 'Speech analysis failed.');
    return data;
  });
}

export function listSpeechAssessments(token) {
  return apiRequest('/orchestrator/speech/history?limit=30', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function deleteSpeechAssessment(token, assessmentId) {
  return fetch(`${API_BASE_URL}/orchestrator/speech/history/${assessmentId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  }).then(async (response) => {
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || 'Could not delete speech assessment.');
    }
  });
}

export function submitQuizAttempt(token, chatId, messageId, answers) {
  return apiRequest('/quiz-attempts', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ chat_id: chatId, message_id: messageId, answers }),
  });
}

export function getQuizAttempts(token, notebookId) {
  return apiRequest(`/quiz-attempts?notebook_id=${notebookId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function searchNearbyResources(token, search, radiusM, category) {
  return apiRequest('/resources/nearby', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      ...search,
      radius_m: radiusM,
      category,
    }),
  });
}

// FILE PURPOSE:
// Provides a centralized frontend API client for authentication,
// chat, notebooks, quiz/speech history, learning tools, and AI agents.
