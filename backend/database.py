"""Data access layer backed by Supabase Postgres.

Every function builds a Supabase client scoped to the calling user's JWT, so
Row Level Security enforces that only that user's rows are visible or writable.
There is no service_role key: the backend cannot bypass RLS, which is exactly
what we want. Supabase calls are synchronous, so they run in a worker thread to
avoid blocking the FastAPI event loop.

Each function takes `token` (the user's access token, used to build the client)
and `user_id` (used to populate / filter the user_id column).
"""
import asyncio
from typing import List, Optional, Dict, Any

from supabase_client import get_user_client


# ---------------------------------------------------------------- conversations

async def create_conversation(
    token: str, user_id: str, title: str = "New Chat", model: str = "mock"
) -> Dict[str, Any]:
    def _run():
        return (
            get_user_client(token)
            .table("conversations")
            .insert({"user_id": user_id, "title": title, "model": model})
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0]


async def get_conversations(token: str, user_id: str) -> List[Dict[str, Any]]:
    def _run():
        return (
            get_user_client(token)
            .table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data or []


async def get_conversation(
    token: str, user_id: str, conv_id: str
) -> Optional[Dict[str, Any]]:
    def _run():
        return (
            get_user_client(token)
            .table("conversations")
            .select("*")
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0] if res.data else None


async def delete_conversation(token: str, user_id: str, conv_id: str) -> None:
    def _run():
        return (
            get_user_client(token)
            .table("conversations")
            .delete()
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .execute()
        )

    await asyncio.to_thread(_run)


async def update_conversation_title(
    token: str, user_id: str, conv_id: str, title: str
) -> None:
    def _run():
        return (
            get_user_client(token)
            .table("conversations")
            .update({"title": title})
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .execute()
        )

    await asyncio.to_thread(_run)


# --------------------------------------------------------------------- messages

async def add_message(
    token: str,
    user_id: str,
    conv_id: str,
    role: str,
    content: str,
    tool_steps: Optional[List[Dict]] = None,
    token_count: Optional[int] = None,
) -> Dict[str, Any]:
    payload = {
        "conversation_id": conv_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "tool_steps": tool_steps,
        "token_count": token_count,
    }

    def _run():
        return get_user_client(token).table("messages").insert(payload).execute()

    res = await asyncio.to_thread(_run)
    return res.data[0]


async def get_messages(token: str, user_id: str, conv_id: str) -> List[Dict[str, Any]]:
    def _run():
        return (
            get_user_client(token)
            .table("messages")
            .select("*")
            .eq("conversation_id", conv_id)
            .eq("user_id", user_id)
            .order("created_at", desc=False)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data or []


# ---------------------------------------------------------------- user_settings

DEFAULT_SETTINGS = {"provider": "mock", "model": "mock", "base_url": None}


async def get_user_settings(token: str, user_id: str) -> Dict[str, Any]:
    def _run():
        return (
            get_user_client(token)
            .table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    if res.data:
        return res.data[0]
    # Row is normally created by the signup trigger; fall back to defaults.
    return {"user_id": user_id, **DEFAULT_SETTINGS}


async def update_user_settings(
    token: str, user_id: str, provider: str, model: str, base_url: Optional[str]
) -> Dict[str, Any]:
    payload = {
        "user_id": user_id,
        "provider": provider,
        "model": model,
        "base_url": base_url,
    }

    def _run():
        return (
            get_user_client(token)
            .table("user_settings")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0]
