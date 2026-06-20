# Sniplink — URL Shortener

Full-stack URL shortener with React + Vite frontend, Flask backend API, MongoDB storage, and Redis caching/rate limiting.

## Folder Structure

```
├── backend/
│   ├── app.py                  # Flask API
│   ├── logging_config.py       # Structured JSON logging
│   ├── requirements.txt        # Python dependencies
│   ├── requirements-dev.txt    # Test dependencies
│   ├── pytest.ini              # Pytest config
│   ├── tests/                  # Backend unit tests
│   └── data/                   # Sample URL documents
├── frontend/
│   ├── src/                    # React source
│   ├── public/                 # Static assets
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── tests/e2e/              # Playwright E2E tests
├── vercel.json                 # Vercel deployment config
├── knowledgebase.md            # Full system documentation
└── .gitignore
```

## Run In Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py          # Flask on :5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # Vite on :8080
```

### Run Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -v   # 25 tests (auth, health, shorten, redirect, stats)
```

## Environment

```
cp .env.example .env
```

Key variables: `MONGO_URI`, `REDIS_HOST`, `AUTH_SECRET`, `SHORT_BASE_URL`.

## API Endpoints

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/api/register` | No | Create account |
| POST | `/api/login` | No | Login |
| POST | `/api/shorten` | Bearer | Create short URL |
| GET | `/api/urls` | Bearer | List user's URLs |
| PUT | `/api/urls/<code>` | Bearer | Update URL |
| DELETE | `/api/urls/<code>` | Bearer | Delete URL |
| GET | `/api/stats/<code>` | No | Click stats |
| GET | `/api/admin/stats` | Bearer | System analytics |
| GET | `/health` | No | Health check |
| GET | `/metrics` | No | In-memory counters |
| GET | `/<short_code>` | No | Redirect |

## Deploy

### Frontend — Vercel

1. Push to GitHub
2. In Vercel Dashboard → Project Settings → **Root Directory**: set to `frontend/`
3. Build command: `npm run build`
4. Output: `dist/`
5. Env var: `VITE_API_BASE_URL=https://urlshortner-1xj7.onrender.com`

### Backend — Render

- Start command: `gunicorn app:app`
- Set env vars: `MONGO_URI`, `REDIS_HOST`, `AUTH_SECRET`, `SHORT_BASE_URL`
