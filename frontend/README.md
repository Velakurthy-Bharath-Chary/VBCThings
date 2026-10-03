# VBC Things Frontend

React and Vite application for the VBC Things learning assistant.

## Local development

1. Install Node.js and npm.
2. From this directory, run `npm ci`.
3. Start the FastAPI backend from `../backend` on `http://127.0.0.1:8010`.
4. Run `npm run dev` and open the URL printed by Vite.

Vite proxies `/api` requests to the local FastAPI backend. The development server may choose port 5174 if 5173 is already in use.

## Checks

- `npm run lint` runs ESLint.
- `npm run build` creates the production frontend bundle in `dist/`.

The frontend does not contain server-side API keys. Authentication tokens are attached by the API service in `src/services/api.js`.
