import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from database import (
    create_conversation,
    get_conversations,
    get_conversation,
    delete_conversation,
    add_message,
    get_messages,
    update_conversation_title,
    get_user_settings,
    update_user_settings,
)
from models import ChatRequest, ConversationCreate, SettingsUpdate
from agent import agent_stream
from auth import get_current_user_id

load_dotenv()


app = FastAPI(title="TASH API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/conversations")
async def list_conversations(user_id: str = Depends(get_current_user_id)):
    return await get_conversations(user_id)


@app.post("/api/conversations")
async def new_conversation(
    body: ConversationCreate, user_id: str = Depends(get_current_user_id)
):
    return await create_conversation(user_id, body.title, body.model)


@app.delete("/api/conversations/{conv_id}")
async def remove_conversation(
    conv_id: str, user_id: str = Depends(get_current_user_id)
):
    await delete_conversation(user_id, conv_id)
    return {"ok": True}


@app.get("/api/conversations/{conv_id}/messages")
async def list_messages(conv_id: str, user_id: str = Depends(get_current_user_id)):
    return await get_messages(user_id, conv_id)


@app.post("/api/chat")
async def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    # Verify the conversation belongs to this user before doing anything.
    conv = await get_conversation(user_id, req.conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    settings = await get_user_settings(user_id)
    history = await get_messages(user_id, req.conversation_id)

    model = req.model if req.model != "auto" else settings.get("model", "mock")
    base_url = req.base_url or settings.get("base_url")
    # LLM API key never comes from the DB: per-request override or the server's own env key.
    api_key = req.api_key or os.getenv("OPENAI_API_KEY")

    await add_message(user_id, req.conversation_id, "user", req.message)

    if len(history) == 0:
        words = req.message.strip().split()
        title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
        await update_conversation_title(user_id, req.conversation_id, title)

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
            await add_message(
                user_id,
                req.conversation_id,
                "assistant",
                final_content,
                collected_steps or None,
            )

    return StreamingResponse(
        generate_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/settings")
async def get_settings(user_id: str = Depends(get_current_user_id)):
    s = await get_user_settings(user_id)
    # Never returns an API key; keys are not persisted.
    return {
        "provider": s.get("provider", "mock"),
        "model": s.get("model", "mock"),
        "base_url": s.get("base_url"),
    }


@app.post("/api/settings")
async def update_settings(
    body: SettingsUpdate, user_id: str = Depends(get_current_user_id)
):
    await update_user_settings(user_id, body.provider, body.model, body.base_url)
    return {"ok": True}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
