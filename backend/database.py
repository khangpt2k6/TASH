"""Data access layer backed by Supabase Postgres.

The backend uses the service_role client (which bypasses RLS), so EVERY function
here scopes its query by `user_id`. Never expose a function that queries without
a user_id filter. Supabase calls are synchronous, so they run in a worker thread
to avoid blocking the FastAPI event loop.
"""
import asyncio
from typing import List, Optional, Dict, Any

from supabase_client import get_service_client


# ---------------------------------------------------------------- conversations

async def create_conversation(
    user_id: str, title: str = "New Chat", model: str = "mock"
) -> Dict[str, Any]:
    def _run():
        return (
            get_service_client()
            .table("conversations")
            .insert({"user_id": user_id, "title": title, "model": model})
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0]


async def get_conversations(user_id: str) -> List[Dict[str, Any]]:
    def _run():
        return (
            get_service_client()
            .table("conversations")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data or []


async def get_conversation(user_id: str, conv_id: str) -> Optional[Dict[str, Any]]:
    def _run():
        return (
            get_service_client()
            .table("conversations")
            .select("*")
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0] if res.data else None


async def delete_conversation(user_id: str, conv_id: str) -> None:
    def _run():
        return (
            get_service_client()
            .table("conversations")
            .delete()
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .execute()
        )

    await asyncio.to_thread(_run)


async def update_conversation_title(user_id: str, conv_id: str, title: str) -> None:
    def _run():
        return (
            get_service_client()
            .table("conversations")
            .update({"title": title})
            .eq("id", conv_id)
            .eq("user_id", user_id)
            .execute()
        )

    await asyncio.to_thread(_run)


# --------------------------------------------------------------------- messages

async def add_message(
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
        return (
            get_service_client().table("messages").insert(payload).execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0]


async def get_messages(user_id: str, conv_id: str) -> List[Dict[str, Any]]:
    def _run():
        return (
            get_service_client()
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


async def get_user_settings(user_id: str) -> Dict[str, Any]:
    def _run():
        return (
            get_service_client()
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
    user_id: str, provider: str, model: str, base_url: Optional[str]
) -> Dict[str, Any]:
    payload = {
        "user_id": user_id,
        "provider": provider,
        "model": model,
        "base_url": base_url,
    }

    def _run():
        return (
            get_service_client()
            .table("user_settings")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )

    res = await asyncio.to_thread(_run)
    return res.data[0]


# ----------------------------------------------------------------- usage_events

async def log_usage(
    user_id: str,
    conv_id: Optional[str],
    model: Optional[str],
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
) -> None:
    payload = {
        "user_id": user_id,
        "conversation_id": conv_id,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }

    def _run():
        return get_service_client().table("usage_events").insert(payload).execute()

    await asyncio.to_thread(_run)
