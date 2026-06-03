import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from database import init_db, create_conversation, get_conversations, delete_conversation, add_message, get_messages, update_conversation_title
from models import ChatRequest, ConversationCreate, SettingsUpdate
from agent import agent_stream

load_dotenv()

SETTINGS_FILE = "settings.json"


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {
        "provider": "mock",
        "model": "mock",
        "api_key": None,
        "base_url": None,
    }


def save_settings(s: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TASH API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/conversations")
async def list_conversations():
    return await get_conversations()


@app.post("/api/conversations")
async def new_conversation(body: ConversationCreate):
    return await create_conversation(body.title, body.model)


@app.delete("/api/conversations/{conv_id}")
async def remove_conversation(conv_id: str):
    await delete_conversation(conv_id)
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/messages")
async def list_messages(conv_id: str):
    return await get_messages(conv_id)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    settings = load_settings()

    history = await get_messages(req.conversation_id)

    model = req.model if req.model != "auto" else settings.get("model", "mock")
    base_url = req.base_url or settings.get("base_url")
    api_key = req.api_key or settings.get("api_key") or os.getenv("OPENAI_API_KEY")

    await add_message(req.conversation_id, "user", req.message)

    if len(history) == 0:
        words = req.message.strip().split()
        title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
        await update_conversation_title(req.conversation_id, title)

    collected_text = []
    collected_steps = []

    async def generate():
        nonlocal collected_text, collected_steps
        async for event in agent_stream(
            req.conversation_id,
            req.message,
            history,
            model,
            base_url,
            api_key,
        ):
            yield event

            if event.startswith("data: "):
                try:
                    data = json.loads(event[6:])
                    if data.get("type") == "text":
                        collected_text.append(data.get("content", ""))
                    elif data.get("type") == "done":
                        collected_steps = data.get("tool_steps", [])
                except Exception:
                    pass

    async def generate_and_save():
        async for chunk in generate():
            yield chunk
        final_content = "".join(collected_text).strip()
        if final_content:
            await add_message(req.conversation_id, "assistant", final_content, collected_steps or None)

    return StreamingResponse(
        generate_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/settings")
async def get_settings():
    s = load_settings()
    if s.get("api_key"):
        s["api_key"] = s["api_key"][:8] + "..." if len(s.get("api_key", "")) > 8 else "***"
    return s


@app.post("/api/settings")
async def update_settings(body: SettingsUpdate):
    current = load_settings()
    updated = {
        "provider": body.provider,
        "model": body.model,
        "api_key": body.api_key or current.get("api_key"),
        "base_url": body.base_url,
    }
    save_settings(updated)
    return {"ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
