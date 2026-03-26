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

## Build Frontend

```
npm run build
```

Flask serves built files from `dist/` at `/`.
