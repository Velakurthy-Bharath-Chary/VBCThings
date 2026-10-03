# Architecture Decisions

## Current design

- FastAPI and Pydantic provide the authenticated REST API and request validation.
- React and Vite provide the browser application.
- PostgreSQL and SQLAlchemy store users, notebooks, documents, conversations, learning artifacts, speech assessments, and quiz attempts.
- JWT and Argon2 authenticate requests and protect user-owned records.
- ChromaDB and BGE embeddings provide persistent, notebook-scoped RAG retrieval.
- LangChain Core formats prompts; Groq handles language generation, image analysis, transcription, and browser search.
- Document uploads are validated and processed synchronously in the API request.
- A local filesystem is the default document store; Supabase Storage is available for hosted document storage.
- Short-lived search caching, upstream request pacing, and API limits use process memory. These are per-process and do not coordinate across multiple instances.
- Newline-delimited JSON streams carry agent selection, tutor chunks, citations, and structured agent results.
- PDF, TXT, Python source, DOCX, and PPTX extraction uses bounded parser input and standard ZIP/XML handling.
- Nearby discovery requests location only after an explicit user action; coordinates are not persisted.
- Speech uploads are discarded after transcription; saved assessments belong to the authenticated user.
- Quiz attempts are scored on the server and scoped to the owning user and notebook.

## Deployment considerations

- Configure the selected FastAPI host, Supabase PostgreSQL, Supabase Storage, Groq credentials, and explicit frontend CORS origins.
- Chroma persists on the API host's disk. Confirm durable storage before deployment; multiple instances require a shared vector-storage design.
- Process-memory cache and request limits are consistent only within one API process. Keep one instance unless shared coordination is added.
- Synchronous ingestion keeps the upload request open while the document is parsed, embedded, and indexed.
