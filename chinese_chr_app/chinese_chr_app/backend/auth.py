import os
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    aud: str | list[str] | None
    iss: str | None
    role: str | None
    user_metadata: dict[str, Any] | None


_jwks_client: PyJWKClient | None = None


def _get_supabase_url() -> str:
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not set")
    return supabase_url


def _get_issuer() -> str:
    # Supabase JWT issuer format: https://<project-ref>.supabase.co/auth/v1
    return f"{_get_supabase_url()}/auth/v1"


def _get_jwks_url() -> str:
    return f"{_get_issuer()}/.well-known/jwks.json"


def _get_expected_audience() -> str:
    # Supabase Auth audience is typically "authenticated" for signed-in users.
    return os.getenv("SUPABASE_JWT_AUD", "authenticated").strip() or "authenticated"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_get_jwks_url())
    return _jwks_client


def verify_bearer_token(bearer_token: str) -> AuthenticatedUser:
    """
    Verify a Supabase Auth access token (JWT) using the project's JWKS.

    Requires:
    - SUPABASE_URL (e.g. https://<project-ref>.supabase.co)
    Optional:
    - SUPABASE_JWT_AUD (default: authenticated)
    """
    token = bearer_token.strip()
    if not token:
        raise jwt.InvalidTokenError("empty_token")

    signing_key = _get_jwks_client().get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        # Supabase signing keys can be ES256 (EC) or RS256 depending on project settings.
        algorithms=["ES256", "RS256"],
        audience=_get_expected_audience(),
        issuer=_get_issuer(),
        options={"require": ["exp", "iat", "sub", "aud", "iss"]},
    )

    return AuthenticatedUser(
        user_id=str(claims.get("sub")),
        aud=claims.get("aud"),
        iss=claims.get("iss"),
        role=claims.get("role"),
        user_metadata=claims.get("user_metadata") or None,
    )


def extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    parts = authorization_header.split()
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None
