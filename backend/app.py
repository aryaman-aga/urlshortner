"""Flask URL shortener API backend.

Exposes REST endpoints for user registration/login, authenticated URL shortening,
public click statistics, and short-code redirects. Persists users and URL mappings in
MongoDB; uses Redis for per-IP rate limiting and redirect URL caching.
"""

from flask import Flask, request, jsonify, redirect, send_from_directory, g
import random
import string
import time
import uuid
import logging
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import redis
from datetime import datetime, timedelta
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from logging_config import log_event, setup_logging
except ModuleNotFoundError:
    from backend.logging_config import log_event, setup_logging

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
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))

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

APP_START_TIME = time.time()
_request_counter = 0
_shorten_counter = 0
_redirect_counter = 0

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_db = int(os.getenv("REDIS_DB", "0"))
redis_password = os.getenv("REDIS_PASSWORD") or None
redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"
try:
    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        db=redis_db,
        ssl=redis_ssl,
        ssl_cert_reqs=None,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
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


@app.before_request
def _init_request_context():
    """Assign a per-request ID, start timer, and increment request metrics."""
    global _request_counter
    _request_counter += 1
    g.request_id = str(uuid.uuid4())
    g._request_start_time = time.perf_counter()


@app.after_request
def _log_request(response):
    """Emit a structured JSON log line for every completed HTTP request."""
    start = getattr(g, "_request_start_time", None)
    duration_ms = (
        round((time.perf_counter() - start) * 1000, 2) if start is not None else None
    )
    log_event(
        logger,
        logging.INFO,
        "request completed",
        event="http_request",
        method=request.method,
        path=request.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


def _ping_mongodb() -> str:
    """Return ``up`` or ``down`` based on a lightweight MongoDB ping."""
    if client is None:
        return "down"
    try:
        client.admin.command("ping")
        return "up"
    except Exception:
        return "down"


def _ping_redis() -> str:
    """Return ``up`` or ``down`` based on a lightweight Redis ping."""
    if redis_client is None:
        return "down"
    try:
        redis_client.ping()
        return "up"
    except Exception:
        return "down"


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
    """Sign a timed auth token embedding the username.

    Args:
        username: Authenticated username to embed in the token payload.

    Returns:
        URL-safe signed token string valid for AUTH_TOKEN_MAX_AGE_SECONDS.
    """
    return _token_serializer.dumps({"u": username})


def _verify_auth_token(token: str) -> str | None:
    """Verify a signed auth token and extract the username.

    Args:
        token: Bearer token from the Authorization header.

    Returns:
        Username string if the token is valid and unexpired; otherwise None.
    """
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
    """Enforce a per-IP request count limit using Redis.

    Args:
        prefix: Redis key prefix (e.g. ``rate_limit_auth`` for auth endpoints).
        max_requests: Maximum allowed requests within the window before rejecting.
        window: Sliding window length in seconds for the Redis key TTL.

    Returns:
        A Flask error response tuple (JSON, 429) when over limit; otherwise None.
        Skips enforcement entirely when Redis is unavailable.
    """
    user_ip = request.remote_addr
    key = f"{prefix}:{user_ip}"
    if redis_client:
        count = redis_client.get(key)
        # Reject once the counter exceeds the allowed maximum for this window.
        if count and int(count) > max_requests:
            log_event(
                logger,
                logging.WARNING,
                "rate limit exceeded",
                event="rate_limit_rejected",
                prefix=prefix,
                path=request.path,
            )
            return jsonify({"error": "Too many requests"}), 429
        redis_client.incr(key)
        redis_client.expire(key, window)
    return None


def _validate_username(username: str) -> str | None:
    """Normalize and validate a username from request input.

    Args:
        username: Raw username value from the JSON body.

    Returns:
        Stripped username if non-empty and at most 64 characters; otherwise None.
    """
    username = (username or "").strip()
    if not username:
        return None
    if len(username) > 64:
        return None
    return username


@app.route("/api/register", methods=["POST"])
def register_user():
    """Create a new user account and return an auth token.

    Request body (JSON):
        username (str, required): Unique username (max 64 chars, used as MongoDB _id).
        password (str, required): Plain-text password (hashed before storage).

    Returns:
        200 JSON ``{"token": str, "username": str}`` on success.

    Error responses:
        400: Missing or invalid username/password.
        409: Username already taken (duplicate _id).
        429: Rate limit exceeded (10 requests/min per IP).
        500: Unexpected failure inserting the user document.
        503: MongoDB unavailable.
    """
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

    # Store only a Werkzeug password hash; never persist the plain-text password.
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
    """Authenticate a user and return an auth token.

    Request body (JSON):
        username (str, required): Registered username.
        password (str, required): Account password.

    Returns:
        200 JSON ``{"token": str, "username": str}`` on success.

    Error responses:
        400: Missing or invalid username/password.
        401: Unknown username or incorrect password.
        429: Rate limit exceeded (10 requests/min per IP).
        503: MongoDB unavailable.
    """
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
    # Use constant-time hash comparison; same 401 for missing user and bad password.
    if not password_hash or not check_password_hash(password_hash, password):
        log_event(
            logger,
            logging.WARNING,
            "login failed",
            event="login_failed",
            username=username,
        )
        return jsonify({"error": "Invalid username or password"}), 401

    token = _create_auth_token(username)
    return jsonify({"token": token, "username": username})

def generate_short_code(length=6):
    """Generate a random alphanumeric short code.

    Args:
        length: Number of characters in the code (default 6).

    Returns:
        Random string drawn from ASCII letters and digits.
    """
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


@app.route('/shorten', methods=['POST'])
@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    """Create or reuse a short URL for the authenticated user.

    Requires ``Authorization: Bearer <token>`` header.

    Request body (JSON):
        url (str, required): Original URL to shorten.
        custom_alias (str, optional): User-chosen short code instead of a random one.
        expiry (str, optional): ISO-8601 datetime after which the link expires.

    Returns:
        200 JSON ``{"short_url": str}`` with the full public short URL.

    Error responses:
        400: Missing url, or custom alias already taken.
        401: Missing or invalid auth token.
        429: Rate limit exceeded (5 requests/min per IP).
        503: MongoDB unavailable.
    """
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
            log_event(
                logger,
                logging.WARNING,
                "rate limit exceeded",
                event="rate_limit_rejected",
                prefix="rate_limit",
                path=request.path,
            )
            return jsonify({"error": "Too many requests"}), 429

        # Track per-IP shorten attempts with a 60-second TTL window.
        redis_client.incr(key)
        redis_client.expire(key, 60)

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
        created = False
    else:
        created = True
        if custom_alias:
            # Check if alias already exists
            if collection.find_one({"short_code": custom_alias}):
                return jsonify({"error": "Custom alias already taken"}), 400
            short_code = custom_alias
        else:
            # Generate a random code and retry on the rare collision with an existing one.
            short_code = generate_short_code()
            while collection.find_one({"short_code": short_code}):
                short_code = generate_short_code()

        collection.insert_one({
            "short_code": short_code,
            "original_url": original_url,
            "user_id": user_id,
            "expiry": expiry,
            "clicks": 0,
            "created_at": datetime.utcnow(),
        })
        global _shorten_counter
        _shorten_counter += 1

    base = _public_base_url()
    short_url = f"{base}/{short_code}"

    log_event(
        logger,
        logging.INFO,
        "url shortened",
        event="shorten_success",
        username=username,
        short_code=short_code,
        newly_created=created,
    )

    return jsonify({"short_url": short_url})

@app.route('/stats/<short_code>', methods=['GET'])
@app.route('/api/stats/<short_code>', methods=['GET'])
def get_stats(short_code):
    """Return public click statistics for a short code.

    Path params:
        short_code (str): The short code to look up.

    Returns:
        200 JSON with ``short_code``, ``original_url``, ``clicks``, and ``expiry``
        (ISO string or null).

    Error responses:
        404: No URL document exists for the given short code.
        503: MongoDB unavailable.
    """
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


@app.route('/health', methods=['GET'])
def deployment_health():
    """Lightweight public health check for uptime monitors and deploy hooks.

    Returns:
        200 when MongoDB and Redis both respond to ping.
        503 when any dependency is unreachable.
    """
    mongodb_status = _ping_mongodb()
    redis_status = _ping_redis()
    all_ok = mongodb_status == "up" and redis_status == "up"
    http_code = 200 if all_ok else 503
    return jsonify({
        "status": "ok" if all_ok else "degraded",
        "mongodb": mongodb_status,
        "redis": redis_status,
        "uptime_seconds": int(time.time() - APP_START_TIME),
    }), http_code


@app.route('/metrics', methods=['GET'])
def metrics():
    """Expose simple in-memory counters since process start (public, no auth)."""
    return jsonify({
        "total_requests": _request_counter,
        "total_redirects": _redirect_counter,
        "total_shortens": _shorten_counter,
        "uptime_seconds": int(time.time() - APP_START_TIME),
    })


@app.route('/aa/admin', methods=['GET'])
@app.route('/aa/admin/', methods=['GET'])
def serve_admin_spa():
    dist_index = os.path.join(PROJECT_ROOT, "dist", "index.html")
    if os.path.exists(dist_index):
        return send_from_directory(os.path.join(PROJECT_ROOT, "dist"), "index.html")
    return jsonify({"error": "Frontend not built"}), 503


@app.route('/<short_code>')
def redirect_url(short_code):
    """Redirect a short code to its original URL and record a click.

    Public endpoint; no authentication required.

    Path params:
        short_code (str): The short code from the URL path.

    Returns:
        302 redirect to the original URL on success.

    Error responses:
        404: Short code not found in MongoDB.
        410: Link has passed its expiry datetime.
        503: MongoDB unavailable.
    """
    global _redirect_counter
    if collection is None:
        return _db_unavailable_response()

    entry = collection.find_one({"short_code": short_code})

    # Reject expired links before serving from cache or DB.
    if entry and entry.get("expiry") and entry["expiry"] < datetime.utcnow():
        return jsonify({"error": "Link expired"}), 410

    if redis_client:
        cached_url = redis_client.get(short_code)
        if cached_url:
            # Cache hit: still increment clicks in MongoDB for accurate stats.
            collection.update_one(
                {"short_code": short_code},
                {"$inc": {"clicks": 1}}
            )
            _redirect_counter += 1
            log_event(
                logger,
                logging.INFO,
                "redirect cache hit",
                event="redirect_cache_hit",
                short_code=short_code,
            )
            return redirect(cached_url.decode('utf-8'))

    if entry:
        original_url = entry["original_url"]

        # Populate Redis on cache miss; entries expire after one hour.
        if redis_client:
            redis_client.set(short_code, original_url, ex=3600)

        collection.update_one(
            {"short_code": short_code},
            {"$inc": {"clicks": 1}}
        )

        _redirect_counter += 1
        log_event(
            logger,
            logging.INFO,
            "redirect cache miss",
            event="redirect_cache_miss",
            short_code=short_code,
        )

        return redirect(original_url)

    else:
        return jsonify({"error": "URL not found"}), 404


@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    if collection is None or db is None:
        return jsonify({"error": "Database unavailable"}), 503

    username = _current_username()
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    urls_total = 0
    urls_expired = 0
    users_total = 0
    try:
        urls_total = len(list(collection.find({}, {"_id": 1}).limit(10000)))
        if urls_total == 10000:
            urls_total = collection.estimated_document_count()
    except Exception as e:
        logger.warning(
            "admin_stats count failed",
            extra={
                "event": "admin_stats_error",
                "error_type": type(e).__name__,
                "error": str(e)[:200],
            },
        )
    try:
        if urls_total:
            expired = list(collection.find({"expiry": {"$lt": datetime.utcnow()}}, {"_id": 1}).limit(10000))
            urls_expired = len(expired)
    except Exception:
        pass
    try:
        users_total = len(list(users.find({}, {"_id": 1}).limit(10000))) if users else 0
    except Exception:
        pass

    clicks_total = 0
    top_urls = []
    try:
        for doc in collection.find({}, {"clicks": 1, "_id": 0}):
            clicks_total += doc.get("clicks", 0) or 0
    except Exception:
        pass
    try:
        top_urls = list(collection.find(
            {},
            {"short_code": 1, "original_url": 1, "clicks": 1, "created_at": 1, "_id": 0}
        ).sort("clicks", -1).limit(10))
    except Exception:
        pass

    db_info = None
    try:
        db_stats = db.command("dbstats")
        db_info = {
            "size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
            "collections": db_stats.get("collections", 0),
            "objects": db_stats.get("objects", 0),
            "avg_object_size_bytes": round(db_stats.get("avgObjSize", 0)),
            "index_size_mb": round(db_stats.get("totalIndexSize", 0) / (1024 * 1024), 2),
        }
    except Exception:
        db_info = {
            "size_mb": 0, "collections": 0, "objects": 0,
            "avg_object_size_bytes": 0, "index_size_mb": 0,
        }

    redis_data = {}
    if redis_client:
        try:
            info = redis_client.info()
            redis_data = {
                "connected": True,
                "keys": redis_client.dbsize(),
                "used_memory_bytes": info.get("used_memory", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0) / max(
                        info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                    ), 4
                ),
            }
        except Exception:
            redis_data = {"connected": False}
    else:
        redis_data = {"connected": False, "configured": False}

    uptime_seconds = int(time.time() - APP_START_TIME)

    return jsonify({
        "urls": {
            "total": urls_total,
            "total_clicks": clicks_total,
            "expired": urls_expired,
        },
        "users": {"total": users_total},
        "database": db_info,
        "redis": redis_data,
        "top_urls": [
            {
                "short_code": u["short_code"],
                "original_url": u["original_url"],
                "clicks": u.get("clicks", 0),
                "created_at": _iso(u.get("created_at")) if u.get("created_at") else None,
            }
            for u in top_urls
        ],
        "system": {
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{uptime_seconds // 86400}d {(uptime_seconds % 86400) // 3600}h {(uptime_seconds % 3600) // 60}m",
            "requests_served": _request_counter,
            "started_at": datetime.fromtimestamp(APP_START_TIME).isoformat(),
        },
    })


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
            {
                "route": "/api/admin/stats",
                "method": "GET",
                "auth": True,
                "rate_limited": False,
                "description": "Full system analysis: URLs, clicks, users, DB size, Redis stats, top URLs, uptime",
                "response": {"urls": "object", "users": "object", "database": "object", "redis": "object", "top_urls": "array", "system": "object"},
                "errors": [401, 503],
            },
            {
                "route": "/api/health",
                "method": "GET",
                "auth": False,
                "rate_limited": False,
                "description": "Health check — pings MongoDB and Redis, returns healthy/degraded status",
                "response": {"status": "healthy|degraded", "checks": {"mongodb": "up|down", "redis": "up|down|disabled"}},
                "errors": [],
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