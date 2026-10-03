# Deployment and local setup

This project uses a lightweight Python setup without containers or schema migration tooling. The backend creates missing SQLAlchemy tables at startup. For an existing database, keep a backup before making schema changes; this setup does not provide migration scripts.

## Local development

1. Create and activate a virtual environment in `backend`.
2. Install `backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and set PostgreSQL, JWT, Groq, and optional Supabase Storage values.
4. Start PostgreSQL locally or set `DATABASE_URL` to the Supabase PostgreSQL session pooler URL with SSL enabled.
5. Run `uvicorn app.main:app --reload --host 127.0.0.1 --port 8010` from `backend`.
6. In another terminal, run `npm ci` then `npm run dev` from `frontend`.

Document uploads are processed synchronously in the API request. Chroma stores embeddings in the backend's local `chroma_db` directory unless `CHROMA_DB_PATH` is set. Uploaded files are local by default; Supabase Storage can be enabled with `DOCUMENT_STORAGE_BACKEND=supabase` and the Supabase settings in the example environment file.

## Production configuration

- Set a strong, unique `JWT_SECRET` (at least 32 characters).
- Set `ENVIRONMENT=production` and explicit `CORS_ORIGINS` for the deployed frontend.
- Configure PostgreSQL, `GROQ_API_KEY`, and `GROQ_MODEL`. The default `openai/gpt-oss-120b` model supports Groq browser search.
- Configure `DOCUMENT_STORAGE_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and a private storage bucket.
- Configure `OVERPASS_API_URL` and an HTTPS `NOMINATIM_BASE_URL` for nearby-place lookup.
- Keep all server credentials in backend environment variables.

The API's caches and per-IP rate limits live in process memory. Use one backend process/instance for consistent behavior. Synchronous ingestion holds the upload request open while parsing, embedding, and indexing a document; embeddings are batched to reduce repeated model overhead.

## Hosting outline

- Frontend: deploy the `frontend` Vite app on Vercel or another static frontend host.
- API: deploy the `backend` FastAPI app on a Python application host.
- Database: Supabase PostgreSQL.
- Document storage: Supabase Storage (optional for local development).
- Vector storage: Chroma persisted on the API host's durable disk. If the host has ephemeral storage or you need multiple API instances, plan a persistent vector-storage design before scaling.

No deployment has been performed by this repository setup. Configure credentials and verify health and application workflows in the chosen hosting accounts.
