from flask import Flask, jsonify, request, g
from flask_cors import CORS
import os
import json
import time
import uuid
import hashlib

# Load environment variables from .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
except ImportError:
    pass  # python-dotenv not installed, skip

from jwt import InvalidTokenError

from auth import extract_bearer_token, verify_bearer_token
from database import init_db, get_all_games, get_or_create_profile, save_game, save_game_with_user, update_profile
from models import db

app = Flask(__name__)
CORS(app)

def _log(event: str, **fields):
    payload = {"event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False))


@app.before_request
def _before_request():
    g._start_time = time.time()
    g.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())


@app.after_request
def _after_request(response):
    try:
        latency_ms = int((time.time() - getattr(g, "_start_time", time.time())) * 1000)
    except Exception:
        latency_ms = None

    _log(
        "http_request",
        request_id=getattr(g, "request_id", None),
        method=request.method,
        path=request.path,
        status=response.status_code,
        latency_ms=latency_ms,
    )
    response.headers["X-Request-Id"] = getattr(g, "request_id", "")
    return response


def _sanitize_display_name(name: str) -> str:
    # Keep it simple and kid-safe.
    cleaned = " ".join((name or "").strip().split())
    cleaned = "".join(ch for ch in cleaned if ch.isprintable())
    return cleaned[:32]


def _default_display_name_from_claims(claims) -> str:
    md = (claims.user_metadata or {}) if claims else {}
    candidate = (
        md.get("name")
        or md.get("full_name")
        or md.get("preferred_username")
        or ""
    )
    candidate = _sanitize_display_name(str(candidate))
    return candidate or "Player"


def _get_authenticated_user_optional():
    token = extract_bearer_token(request.headers.get("Authorization"))
    if not token:
        return None, None
    try:
        user = verify_bearer_token(token)
        return user, None
    except InvalidTokenError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def _get_authenticated_user_required():
    user, err = _get_authenticated_user_optional()
    if user is None:
        raise PermissionError(err or "missing_authorization")
    return user


# Initialize database
try:
    init_db(app)
except Exception as e:
    print(f"Warning: Database initialization failed: {e}")
    print("Make sure DATABASE_URL environment variable is set")

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/api/profile', methods=['GET'])
def get_profile():
    """Get or create the current user's profile."""
    try:
        user = _get_authenticated_user_required()
        with app.app_context():
            profile = get_or_create_profile(
                user_id=user.user_id,
                default_display_name=_default_display_name_from_claims(user),
            )
            return jsonify({"profile": {"display_name": profile.display_name}}), 200
    except PermissionError as e:
        _log("auth_failed", request_id=getattr(g, "request_id", None), error=str(e))
        return jsonify({"error": "Unauthorized"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/profile', methods=['PUT'])
def put_profile():
    """Update the current user's profile."""
    try:
        user = _get_authenticated_user_required()
        data = request.get_json() or {}
        display_name = _sanitize_display_name(str(data.get("display_name") or ""))
        if not display_name:
            return jsonify({"error": "display_name is required"}), 400
        if len(display_name) > 32:
            return jsonify({"error": "display_name must be 32 characters or less"}), 400

        with app.app_context():
            profile = update_profile(user_id=user.user_id, display_name=display_name)
            _log(
                "profile_updated",
                request_id=getattr(g, "request_id", None),
                user_id_hash=hashlib.sha256(user.user_id.encode("utf-8")).hexdigest()[:12],
            )
            return jsonify({"profile": {"display_name": profile.display_name}}), 200
    except PermissionError as e:
        _log("auth_failed", request_id=getattr(g, "request_id", None), error=str(e))
        return jsonify({"error": "Unauthorized"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/games', methods=['POST'])
def create_game():
    """Save a game result"""
    try:
        data = request.get_json() or {}

        # Optional auth: if present and valid, use profile display name snapshot.
        auth_user, auth_error = _get_authenticated_user_optional()

        # Validate required fields
        required_fields = ['time_elapsed', 'rounds', 'total_questions']
        if not auth_user:
            required_fields.append('name')
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        if auth_user:
            with app.app_context():
                profile = get_or_create_profile(
                    user_id=auth_user.user_id,
                    default_display_name=_default_display_name_from_claims(auth_user),
                )
                display_name = profile.display_name
                game_data = save_game_with_user(
                    user_id=auth_user.user_id,
                    name=display_name,
                    time_elapsed=data["time_elapsed"],
                    rounds=data["rounds"],
                    total_questions=data["total_questions"],
                )
        else:
            if auth_error:
                _log("auth_invalid", request_id=getattr(g, "request_id", None), error=auth_error)
            game_data = save_game(
                name=data['name'],
                time_elapsed=data['time_elapsed'],  # in milliseconds
                rounds=data['rounds'],
                total_questions=data['total_questions']
            )

        _log(
            "game_saved",
            request_id=getattr(g, "request_id", None),
            authenticated=bool(auth_user),
            time_elapsed=data.get("time_elapsed"),
            rounds=data.get("rounds"),
            total_questions=data.get("total_questions"),
            display_name_len=len(str(game_data.get("name") or "")),
        )
        
        return jsonify({'success': True, 'game': game_data}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/games', methods=['GET'])
def get_games():
    """Get all games (for leaderboard)"""
    try:
        games = get_all_games()
        return jsonify({'games': games}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
