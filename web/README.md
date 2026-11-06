# FastBreak web app

Next.js front end for FastBreak. It talks to the FastBreak API (`uv run fastbreak serve`
in the repo root), which runs on the PC with the database and the model.

```bash
cp .env.example .env.local   # FASTBREAK_API_URL, and FASTBREAK_API_KEY if the API has one
npm install
npm run dev                  # http://localhost:3000
```

- `/` — the question box and last night's games
- `/ask?q=...` — one answer, streamed step by step from the API
- `/api/ask` — passes a question to the FastBreak API and streams its events back. It
  adds the API key on the server, so the browser never sees it.

The API answers one question at a time; a second question while one is running gets a
"busy" message.
