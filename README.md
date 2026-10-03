# VBC Things - Agentic Learning Assistant

A learning assistant with a React/Vite frontend and FastAPI backend. It combines PostgreSQL-backed notebooks and chat with LangChain prompt construction, BGE embeddings, ChromaDB retrieval, and Groq-powered tutoring. The platform also includes quizzes, summaries, notes, flashcards, study guides, image analysis, speech analysis, web resource search, and nearby learning-place discovery.

## Stack

- React + Vite
- FastAPI, SQLAlchemy, Pydantic, JWT, and Argon2
- Supabase PostgreSQL (or local PostgreSQL for development)
- LangChain Core, BGE embeddings, and ChromaDB
- Groq as the single AI API for tutoring, image analysis, transcription, and browser search
- Synchronous document ingestion with batch embeddings

ChromaDB persists vectors locally. Search-result caching and request limits are in process memory, so use one backend process for consistent behavior.

## Local development

Create and activate a Python 3.10+ virtual environment in `backend`, install `requirements.txt`, then configure `backend/.env` from `backend/.env.example`. Start PostgreSQL (or configure Supabase PostgreSQL), then run `uvicorn app.main:app --reload --host 127.0.0.1 --port 8010` from `backend`.

Run the frontend separately with `npm ci` and `npm run dev` from `frontend`. Its Vite development proxy targets the API on port 8010.

## Main workflows

- Create an account, sign in, and create a notebook.
- Upload PDF, TXT, Python source, DOCX, and PPTX documents.
- Ask questions grounded in uploaded sources; responses include source citations when matching context is available.
- Use orchestrated tutoring, quizzes, image analysis, summaries, flashcards, notes, and study guides.
- Search the web using Groq's built-in browser search and find nearby libraries, colleges, and study spaces.
- Use speech analysis to transcribe and review language signals.

## Configuration and deployment

Backend settings are documented in [backend/.env.example](backend/.env.example). Keep database and provider credentials on the backend; do not put server secrets in frontend variables. See [DEPLOYMENT.md](DEPLOYMENT.md) for Supabase PostgreSQL and Storage configuration and hosting notes.

The API exposes `/health`, `/health/db`, and `/health/ready`. Production deployment still requires a valid Groq key, a strong JWT secret, explicit CORS origins, Supabase Storage configuration, and suitable geocoding service configuration.
