# URL Shortener Project

Clean full-stack layout with:
- React + Vite frontend
- Flask backend API
- MongoDB for storage
- Redis for cache/rate limiting

## Folder Structure

```
backend/
	app.py                  # Main Flask backend
	requirements.txt        # Backend Python dependencies
	data/
		urls.json             # Sample/exported URL documents

src/                      # Frontend source (React)
public/                   # Frontend static files
tests/e2e/                # Playwright config and fixture

archive/
	package-copy.json       # Old package backup

app.py                    # Root compatibility launcher for backend
requirements.txt          # Includes backend/requirements.txt
vite.config.ts            # Frontend dev/build config
```

## Run In Development

1. Backend

```
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

2. Frontend

```
npm install
npm run dev
```

## Environment

Copy and edit:

```
cp .env.example .env
```

Useful variables:
- `PORT`
- `MONGO_URI`
- `REDIS_HOST`
- `SHORT_BASE_URL`
- `AUTH_SECRET` (required for login tokens)

## Auth (Username + Password)

This project now supports a simple login system:

- Register: `POST /api/register` with `{ "username": "...", "password": "..." }`
- Login: `POST /api/login` with `{ "username": "...", "password": "..." }`

The frontend stores a Bearer token and automatically sends it on:

- `POST /api/shorten` (protected)
- `GET /api/urls` (protected)

These stay public:

- `GET /api/stats/<short_code>`
- `GET /<short_code>` (redirect)

## Build Frontend

```
npm run build
```

Flask serves built files from `dist/` at `/` when you want a single Render service.

## Deploy Frontend to Vercel

The frontend is a Vite app and can be deployed to Vercel as a static site.

**Build settings (in Vercel dashboard):**
- Framework preset: Vite
- Build command: `npm run build`
- Output directory: `dist`

**Environment variables (Vercel → Project → Settings → Environment Variables):**
- `VITE_API_BASE_URL=https://urlshortner-1xj7.onrender.com`

After setting the env var, trigger a new deployment. The Vercel-hosted frontend will call the Flask API on Render via the `/api/...` routes.
