# Child Agent Web

Plain HTML/CSS/JS client for the Child-Grounded Story Agent — no build step,
no framework. `index.html` loads `style.css` and `app.js` directly.

Drives the closed loop against the Core API: camera capture → drawing
revision grounding (`/v1/sessions/{id}/drawing-revisions/*`) → story
proposal grounding (`/v1/sessions/{id}/story/proposals/*`) → full story with
optional TTS playback (`/v1/tts`). The frontend never owns canonical
state — every action round-trips through the API.

## Local development

No install step required. Run `make dev-api` from the repo root and open
`http://localhost:8000` — FastAPI serves this directory same-origin, so
there's no CORS to configure.
