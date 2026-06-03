"""JWT authentication for the TASH API.

Every protected endpoint depends on `get_current_user`, which validates the
Supabase access token by calling GoTrue's `/auth/v1/user` endpoint. This works
regardless of whether the project signs JWTs with a symmetric secret or
asymmetric keys, and returns the authenticated user's id.

The user response is cached briefly so a burst of requests with the same token
doesn't hit GoTrue every time.
"""
import os
import time
from dataclasses import dataclass
from typing import Dict

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_bearer = HTTPBearer(auto_error=False)

# token -> (user dict, expires_at monotonic seconds)
_CACHE: Dict[str, tuple] = {}
_CACHE_TTL = 30.0


async def _fetch_user(token: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_ANON_KEY,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return resp.json()


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Resolve and return the authenticated Supabase user, or raise 401."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    token = creds.credentials
    now = time.monotonic()

    cached = _CACHE.get(token)
    if cached and cached[1] > now:
        return cached[0]

    user = await _fetch_user(token)
    _CACHE[token] = (user, now + _CACHE_TTL)
    # opportunistic cleanup of expired entries
    if len(_CACHE) > 512:
        for k in [k for k, v in _CACHE.items() if v[1] <= now]:
            _CACHE.pop(k, None)
    return user


async def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    uid = user.get("id")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token did not resolve to a user id",
        )
    return uid


@dataclass
class AuthContext:
    """The authenticated user's id plus their raw access token.

    The token is forwarded to Supabase so PostgREST queries run under that
    user's RLS context.
    """

    user_id: str
    token: str


async def get_auth(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    user: dict = Depends(get_current_user),
) -> AuthContext:
    uid = user.get("id")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token did not resolve to a user id",
        )
    return AuthContext(user_id=uid, token=creds.credentials)
