"""
Google Sign-In — ID token verification.

Uses the Google Identity Services ID-token flow: the frontend obtains a Google
ID token and posts it here; we verify its signature and audience against
GOOGLE_CLIENT_ID using the google-auth library (already installed as a
transitive dependency). No second auth system -- callers issue the app's normal
JWT afterwards.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings


def google_enabled() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID)


def verify_google_id_token(token: str) -> dict:
    """
    Verify a Google ID token and return the verified claims.

    Returns a dict with: sub, email, email_verified, name, picture.
    Raises 503 if Google sign-in is not configured, 401 if the token is invalid.
    """
    if not google_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on this server.",
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential.",
        )

    if not claims.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account did not provide an email address.",
        )
    if not claims.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Google email address is not verified.",
        )

    return {
        "sub": claims["sub"],
        "email": claims["email"].lower(),
        "email_verified": True,
        "name": claims.get("name", ""),
        "picture": claims.get("picture"),
    }
