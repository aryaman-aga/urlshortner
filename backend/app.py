from flask import Flask, request, jsonify, redirect, send_from_directory
import random
import string
from pymongo import MongoClient
import redis
from datetime import datetime, timedelta
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except Exception:
    load_dotenv = None

try:
    from flask_cors import CORS
except Exception:
    CORS = None


app = Flask(__name__)

if CORS is not None:
    CORS(app, resources={r"/api/*": {"origins": os.getenv("CORS_ORIGINS", "*")}})

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_db = int(os.getenv("REDIS_DB", "0"))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017/"
mongo_db_name = os.getenv("MONGO_DB", "url_shortener")
mongo_collection_name = os.getenv("MONGO_COLLECTION", "urls")

client = MongoClient(mongo_uri)
db = client[mongo_db_name]
collection = db[mongo_collection_name]
# Compound unique index (user_id + original_url + expiry)
collection.create_index(
    [("user_id", 1), ("original_url", 1), ("expiry", 1)],
    unique=True
)


def _iso(dt: datetime | None):
    if not dt:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def _parse_expiry(value: str | None):
    if not value:
        return None
    try:
        # Handle ISO strings from the frontend (e.g. "YYYY-MM-DDTHH:mm" or "...Z")
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _public_base_url() -> str:
    # If set, always use this public domain for generated short URLs.
    # Example: SHORT_BASE_URL=https://urlshortner.ly
    configured = os.getenv("SHORT_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return request.host_url.rstrip("/")

# Generate short code
def generate_short_code(length=6):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Optional: Base62 encoding for better short codes (future upgrade)
def base62_encode(num):
    characters = string.ascii_letters + string.digits
    base = len(characters)
    encoded = ""
    while num > 0:
        encoded = characters[num % base] + encoded
        num //= base
    return encoded or "0"


# API 1: Shorten URL
@app.route('/shorten', methods=['POST'])
@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()

    # Simple rate limiting (per IP)
    user_ip = request.remote_addr
    key = f"rate_limit:{user_ip}"

    requests_count = redis_client.get(key)
    if requests_count and int(requests_count) > 5:
        return jsonify({"error": "Too many requests"}), 429

    redis_client.incr(key)
    redis_client.expire(key, 60)  # 1 minute window

    original_url = data.get("url")
    custom_alias = data.get("custom_alias")

    if not original_url:
        return jsonify({"error": "URL is required"}), 400

    # Hardcoded user_id (for now)
    user_id = "user123"
    expiry = _parse_expiry(data.get("expiry"))

    # Optional expiry (1 day)
    # expiry = datetime.utcnow() + timedelta(days=1)

    # Check if same URL already exists for this user + expiry
    existing = collection.find_one({
        "original_url": original_url,
        "user_id": user_id,
        "expiry": expiry
    })

    if existing:
        short_code = existing["short_code"]
    else:
        if custom_alias:
            # Check if alias already exists
            if collection.find_one({"short_code": custom_alias}):
                return jsonify({"error": "Custom alias already taken"}), 400
            short_code = custom_alias
        else:
            short_code = generate_short_code()
            while collection.find_one({"short_code": short_code}):
                short_code = generate_short_code()

        collection.insert_one({
            "short_code": short_code,
            "original_url": original_url,
            "user_id": user_id,
            "expiry": expiry,
            "clicks": 0
        })

    base = _public_base_url()
    short_url = f"{base}/{short_code}"

    return jsonify({"short_url": short_url})

# API 3: Analytics (click stats)
@app.route('/stats/<short_code>', methods=['GET'])
@app.route('/api/stats/<short_code>', methods=['GET'])
def get_stats(short_code):
    entry = collection.find_one({"short_code": short_code})

    if not entry:
        return jsonify({"error": "URL not found"}), 404

    return jsonify({
        "short_code": short_code,
        "original_url": entry["original_url"],
        "clicks": entry.get("clicks", 0),
        "expiry": _iso(entry.get("expiry"))
    })


@app.route('/api/urls', methods=['GET'])
def list_urls():
    # Hardcoded user_id for now (to match shorten endpoint)
    user_id = "user123"
    limit = min(int(request.args.get("limit", 100)), 500)
    skip = max(int(request.args.get("skip", 0)), 0)

    cursor = (
        collection.find({"user_id": user_id}, {"_id": 0})
        .sort([("clicks", -1)])
        .skip(skip)
        .limit(limit)
    )

    items = []
    base = _public_base_url()
    for doc in cursor:
        items.append({
            "short_code": doc.get("short_code"),
            "original_url": doc.get("original_url"),
            "clicks": doc.get("clicks", 0),
            "expiry": _iso(doc.get("expiry")),
            "short_url": f"{base}/{doc.get('short_code')}" if doc.get("short_code") else None,
        })

    return jsonify({"items": items, "limit": limit, "skip": skip})


# API 2: Redirect
@app.route('/<short_code>')
def redirect_url(short_code):
    
    # 🔥 Step 1: Check Redis
    entry = collection.find_one({"short_code": short_code})

# Expiry check first
    if entry and entry.get("expiry") and entry["expiry"] < datetime.utcnow():
        return jsonify({"error": "Link expired"}), 410

# Then Redis
    cached_url = redis_client.get(short_code)
    if cached_url:
        # Increment clicks even on cache hit
        collection.update_one(
            {"short_code": short_code},
            {"$inc": {"clicks": 1}}
        )
        return redirect(cached_url.decode('utf-8'))

    # ❌ Cache miss → go to DB

    if entry:
        original_url = entry["original_url"]

        # Cache with TTL (1 hour)
        redis_client.set(short_code, original_url, ex=3600)

        # Increment clicks
        collection.update_one(
            {"short_code": short_code},
            {"$inc": {"clicks": 1}}
        )

        return redirect(original_url)

    else:
        return jsonify({"error": "URL not found"}), 404


@app.route('/', methods=['GET'])
def serve_frontend_root():
    dist_index = os.path.join(PROJECT_ROOT, "dist", "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(os.path.join(PROJECT_ROOT, "dist"), "index.html")
    return jsonify({
        "message": "Frontend not built yet. Run `npm run build` to create dist/.",
        "api": ["/api/shorten", "/api/stats/<short_code>", "/api/urls"],
    })


@app.route('/assets/<path:filename>', methods=['GET'])
def serve_frontend_assets(filename):
    dist_assets = os.path.join(PROJECT_ROOT, "dist", "assets")
    if os.path.exists(dist_assets):
        return send_from_directory(dist_assets, filename)
    return jsonify({"error": "Frontend assets not found"}), 404


if __name__ == '__main__':
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=True)