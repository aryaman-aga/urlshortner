from flask import Flask, request, jsonify, redirect, send_from_directory
import random
import string
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import redis
from datetime import datetime, timedelta
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

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

def _parse_cors_origins(value: str):
    value = (value or "").strip()
    if not value or value == "*":
        return "*"
    return [v.strip() for v in value.split(",") if v.strip()]


if CORS is not None:
    CORS(
        app,
        resources={r"/api/*": {"origins": _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))}},
        allow_headers=["Content-Type", "Authorization"],
    )


AUTH_SECRET = os.getenv("AUTH_SECRET") or os.getenv("SECRET_KEY") or "dev-secret"
AUTH_TOKEN_MAX_AGE_SECONDS = int(os.getenv("AUTH_TOKEN_MAX_AGE_SECONDS", "604800"))  # 7 days
_token_serializer = URLSafeTimedSerializer(AUTH_SECRET, salt="sniplink-auth")

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_db = int(os.getenv("REDIS_DB", "0"))
try:
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
    redis_client.ping()
except Exception:
    redis_client = None

mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017/"
mongo_db_name = os.getenv("MONGO_DB", "url_shortener")
mongo_collection_name = os.getenv("MONGO_COLLECTION", "urls")

client = None
db = None
collection = None
users = None

try:
    # Keep startup non-fatal on platforms like Render when DB is temporarily unavailable.
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client[mongo_db_name]
    collection = db[mongo_collection_name]
    users = db["users"]
    # Indexes for query performance
    collection.create_index(
        [("user_id", 1), ("original_url", 1), ("expiry", 1)],
        unique=True
    )
    collection.create_index("short_code", unique=True)
    collection.create_index([("user_id", 1), ("clicks", -1)])
    collection.create_index("user_id")
except Exception:
    client = None
    db = None
    collection = None
    users = None


def _db_unavailable_response():
    return jsonify({"error": "Database unavailable. Set a valid MONGO_URI and restart."}), 503


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


def _create_auth_token(username: str) -> str:
    return _token_serializer.dumps({"u": username})


def _verify_auth_token(token: str) -> str | None:
    try:
        data = _token_serializer.loads(token, max_age=AUTH_TOKEN_MAX_AGE_SECONDS)
    except (SignatureExpired, BadSignature):
        return None
    except Exception:
        return None

    if isinstance(data, dict):
        username = data.get("u")
    else:
        username = data

    if not username:
        return None
    return str(username)


def _current_username() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return _verify_auth_token(parts[1])


def _require_auth_username():
    username = _current_username()
    if not username:
        return None, (jsonify({"error": "Unauthorized"}), 401)
    return username, None


def _check_rate_limit(prefix: str = "rate_limit", max_requests: int = 10, window: int = 60):
    user_ip = request.remote_addr
    key = f"{prefix}:{user_ip}"
    if redis_client:
        count = redis_client.get(key)
        if count and int(count) > max_requests:
            return jsonify({"error": "Too many requests"}), 429
        redis_client.incr(key)
        redis_client.expire(key, window)
    return None


def _validate_username(username: str) -> str | None:
    username = (username or "").strip()
    if not username:
        return None
    if len(username) > 64:
        return None
    return username


@app.route("/api/register", methods=["POST"])
def register_user():
    if users is None:
        return _db_unavailable_response()

    rate_error = _check_rate_limit("rate_limit_auth", max_requests=10, window=60)
    if rate_error:
        return rate_error

    data = request.get_json(silent=True) or {}
    username = _validate_username(data.get("username"))
    password = (data.get("password") or "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    password_hash = generate_password_hash(password)
    try:
        users.insert_one({"_id": username, "password_hash": password_hash})
    except DuplicateKeyError:
        return jsonify({"error": "Username already taken, choose another"}), 409
    except Exception:
        return jsonify({"error": "Failed to create account"}), 500

    token = _create_auth_token(username)
    return jsonify({"token": token, "username": username})


@app.route("/api/login", methods=["POST"])
def login_user():
    if users is None:
        return _db_unavailable_response()

    rate_error = _check_rate_limit("rate_limit_auth", max_requests=10, window=60)
    if rate_error:
        return rate_error

    data = request.get_json(silent=True) or {}
    username = _validate_username(data.get("username"))
    password = (data.get("password") or "")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = users.find_one({"_id": username})
    password_hash = (user or {}).get("password_hash")
    if not password_hash or not check_password_hash(password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = _create_auth_token(username)
    return jsonify({"token": token, "username": username})

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
    if collection is None:
        return _db_unavailable_response()

    username, error_response = _require_auth_username()
    if error_response:
        return error_response

    data = request.get_json()

    # Simple rate limiting (per IP)
    user_ip = request.remote_addr
    key = f"rate_limit:{user_ip}"

    if redis_client:
        requests_count = redis_client.get(key)
        if requests_count and int(requests_count) > 5:
            return jsonify({"error": "Too many requests"}), 429

        redis_client.incr(key)
        redis_client.expire(key, 60)  # 1 minute window

    original_url = data.get("url")
    custom_alias = data.get("custom_alias")

    if not original_url:
        return jsonify({"error": "URL is required"}), 400

    user_id = username
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
    if collection is None:
        return _db_unavailable_response()

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
    if collection is None:
        return _db_unavailable_response()

    username, error_response = _require_auth_username()
    if error_response:
        return error_response

    user_id = username
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


@app.route('/api/urls/<short_code>', methods=['PUT'])
def update_url(short_code):
    if collection is None:
        return _db_unavailable_response()

    username, error_response = _require_auth_username()
    if error_response:
        return error_response

    data = request.get_json(silent=True) or {}
    existing = collection.find_one({"short_code": short_code, "user_id": username})

    if not existing:
        return jsonify({"error": "URL not found"}), 404

    update_fields = {}
    if "url" in data:
        update_fields["original_url"] = data["url"]
    if "expiry" in data:
        update_fields["expiry"] = _parse_expiry(data.get("expiry"))
    if "custom_alias" in data and data["custom_alias"]:
        new_alias = data["custom_alias"]
        if collection.find_one({"short_code": new_alias, "_id": {"$ne": existing["_id"]}}):
            return jsonify({"error": "Custom alias already taken"}), 400
        update_fields["short_code"] = new_alias
        if redis_client:
            redis_client.delete(short_code)

    if not update_fields:
        return jsonify({"error": "No fields to update"}), 400

    collection.update_one({"short_code": short_code, "user_id": username}, {"$set": update_fields})

    if redis_client:
        redis_client.delete(short_code)

    base = _public_base_url()
    new_short_code = update_fields.get("short_code", short_code)
    return jsonify({"short_url": f"{base}/{new_short_code}"})


@app.route('/api/urls/<short_code>', methods=['DELETE'])
def delete_url(short_code):
    if collection is None:
        return _db_unavailable_response()

    username, error_response = _require_auth_username()
    if error_response:
        return error_response

    result = collection.delete_one({"short_code": short_code, "user_id": username})

    if result.deleted_count == 0:
        return jsonify({"error": "URL not found"}), 404

    if redis_client:
        redis_client.delete(short_code)

    return jsonify({"message": "Deleted"}), 200


# API 2: Redirect
@app.route('/<short_code>')
def redirect_url(short_code):
    if collection is None:
        return _db_unavailable_response()

    
    # Step 1: Check Redis cache
    entry = collection.find_one({"short_code": short_code})

# Expiry check first
    if entry and entry.get("expiry") and entry["expiry"] < datetime.utcnow():
        return jsonify({"error": "Link expired"}), 410

# Then Redis
    if redis_client:
        cached_url = redis_client.get(short_code)
        if cached_url:
            # Increment clicks even on cache hit
            collection.update_one(
                {"short_code": short_code},
                {"$inc": {"clicks": 1}}
            )
            return redirect(cached_url.decode('utf-8'))

    # Cache miss — fall back to DB

    if entry:
        original_url = entry["original_url"]

        # Cache with TTL (1 hour)
        if redis_client:
            redis_client.set(short_code, original_url, ex=3600)

        # Increment clicks
        collection.update_one(
            {"short_code": short_code},
            {"$inc": {"clicks": 1}}
        )

        return redirect(original_url)

    else:
        return jsonify({"error": "URL not found"}), 404


@app.route('/api/health', methods=['GET'])
def health_check():
    status = "healthy"
    checks = {}

    try:
        client.admin.command("ping")
        checks["mongodb"] = "up"
    except Exception:
        checks["mongodb"] = "down"
        status = "degraded"

    if redis_client:
        try:
            redis_client.ping()
            checks["redis"] = "up"
        except Exception:
            checks["redis"] = "down"
            status = "degraded"
    else:
        checks["redis"] = "disabled"

    http_code = 200 if status == "healthy" else 503
    return jsonify({
        "status": status,
        "checks": checks,
    }), http_code


@app.route('/api', methods=['GET'])
def api_docs():
    return jsonify({
        "name": "Sniplink API",
        "version": "1.0.0",
        "endpoints": [
            {
                "route": "/api/register",
                "method": "POST",
                "auth": False,
                "rate_limited": True,
                "description": "Create a new account",
                "request_body": {"username": "string", "password": "string"},
                "response": {"token": "string", "username": "string"},
                "errors": [400, 409, 429, 503],
            },
            {
                "route": "/api/login",
                "method": "POST",
                "auth": False,
                "rate_limited": True,
                "description": "Login and receive an auth token",
                "request_body": {"username": "string", "password": "string"},
                "response": {"token": "string", "username": "string"},
                "errors": [400, 401, 429, 503],
            },
            {
                "route": "/api/shorten",
                "method": "POST",
                "auth": True,
                "rate_limited": True,
                "description": "Create a short URL",
                "request_body": {"url": "string (required)", "custom_alias": "string (optional)", "expiry": "ISO datetime (optional)"},
                "response": {"short_url": "string"},
                "errors": [400, 401, 429, 503],
            },
            {
                "route": "/api/urls",
                "method": "GET",
                "auth": True,
                "rate_limited": False,
                "description": "List the authenticated user's short URLs, sorted by clicks descending",
                "query_params": {"limit": "int (default 100, max 500)", "skip": "int (default 0)"},
                "response": {"items": "array", "limit": "int", "skip": "int"},
                "errors": [401, 503],
            },
            {
                "route": "/api/urls/<short_code>",
                "method": "PUT",
                "auth": True,
                "rate_limited": False,
                "description": "Update a short URL's destination, alias, or expiry",
                "request_body": {"url": "string (optional)", "custom_alias": "string (optional)", "expiry": "ISO datetime or null (optional)"},
                "response": {"short_url": "string"},
                "errors": [400, 401, 404, 503],
            },
            {
                "route": "/api/urls/<short_code>",
                "method": "DELETE",
                "auth": True,
                "rate_limited": False,
                "description": "Delete a short URL and its click data",
                "response": {"message": "Deleted"},
                "errors": [401, 404, 503],
            },
            {
                "route": "/api/stats/<short_code>",
                "method": "GET",
                "auth": False,
                "rate_limited": False,
                "description": "Get public click statistics for any short URL",
                "response": {"short_code": "string", "original_url": "string", "clicks": "int", "expiry": "ISO datetime or null"},
                "errors": [404],
            },
            {
                "route": "/<short_code>",
                "method": "GET",
                "auth": False,
                "rate_limited": False,
                "description": "Redirect to the original URL (cached via Redis, TTL 1 hour)",
                "response": "302 redirect or 410 if expired",
                "errors": [404, 410],
            },
        ],
    })


@app.route('/', methods=['GET'])
@app.route('/login', methods=['GET'])
@app.route('/register', methods=['GET'])
def serve_frontend_root():
    dist_index = os.path.join(PROJECT_ROOT, "dist", "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(os.path.join(PROJECT_ROOT, "dist"), "index.html")
    return jsonify({
        "message": "Frontend not built yet. Run `npm run build` to create dist/.",
        "api_docs": "/api",
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