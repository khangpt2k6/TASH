"""Supabase client setup.

The backend acts as a trusted gateway: it uses the service_role key for all
database operations (which bypasses RLS) but only after verifying the caller's
JWT and scoping every query to that user's id. RLS remains enabled on every
table as defense in depth.
"""
import os
from functools import lru_cache

from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """Return a cached Supabase client authenticated with the service_role key.

    This client bypasses RLS, so callers MUST scope every query by user_id.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment "
            "(see backend/.env.example)."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
