# Project Status

Last reviewed: 2026-10-01

## Current implementation

- Authentication uses JWT and Argon2. Notebooks, documents, conversations, quizzes, artifacts, and speech assessments are scoped to the authenticated owner.
- Document retrieval uses BGE embeddings with ChromaDB. PDF, TXT, Python source, DOCX, and PPTX uploads are validated and processed synchronously; document chunks are embedded in batches.
- Chat requests use the orchestrator stream for tutor, quiz, resource, and image-agent routing. Tutor output streams with citations; quizzes are interactive and scored on the server; web results render as resource cards.
- Groq is the single AI provider. It handles generation and browser-based web search using the configured supported GPT-OSS model.
- Image analysis and speech analysis are available in the learning workspace. Speech transcripts and assessment records can be managed by the authenticated user.
- The Learning Studio supports notes, summaries, flashcards, quizzes, and study guides, with notebook-scoped loading and deletion.
- Nearby learning-place search supports user-initiated location or a typed city/town and presents OpenStreetMap attribution.
- Search-result caches, upstream pacing, and per-IP request limits are process-local. They are not shared across multiple API processes.
- Document ingestion is synchronous. The backend creates missing SQLAlchemy tables on startup; this project copy does not include schema migration tooling or container orchestration.
- Scheduling and peer-session features are intentionally excluded from this project copy.

## External setup still required

- Supply Supabase PostgreSQL and, if desired, Supabase Storage configuration in the backend environment.
- Supply a valid Groq API key and configure frontend origins before hosting.
- Choose a deployment host with durable disk for Chroma and confirm upload/request timeouts for synchronous ingestion.
- Configure a suitable nearby-search provider for expected production traffic.
- No hosted deployment or live cloud-provider connection is claimed by this status document.

## Verification status

Run the backend checks in the local environment after installing the current requirements and configuring a test database. Provider-backed behavior requires valid Groq credentials.
