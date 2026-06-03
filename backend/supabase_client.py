"""Supabase client setup.

The backend does NOT use a service_role key. Instead, each request builds a
Supabase client authenticated with the calling user's JWT and forwards it to
PostgREST. Row Level Security then enforces that the user can only touch their
own rows. This means there is no server-side secret to manage: the only key the
backend needs is the public anon/publishable key (used as the `apikey` header).
"""
import os

from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def get_user_client(access_token: str) -> Client:
    """Return a Supabase client scoped to the user identified by `access_token`.

    A fresh client is created per request so concurrent requests never share
    mutable auth state. RLS runs as the authenticated user, so every query is
    automatically constrained to that user's rows.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment "
            "(see backend/.env.example)."
        )
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    # Send the user's JWT as the PostgREST bearer token so RLS applies as them.
    client.postgrest.auth(access_token)
    return client
