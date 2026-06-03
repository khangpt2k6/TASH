import aiosqlite
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

DB_PATH = "tash.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'mock',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_steps TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        await db.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_conversation(title: str = "New Chat", model: str = "mock") -> Dict[str, Any]:
    conv_id = str(uuid.uuid4())
    ts = now_iso()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, title, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title, model, ts, ts)
        )
        await db.commit()
    return {"id": conv_id, "title": title, "model": model, "created_at": ts, "updated_at": ts}


async def get_conversations() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_conversation(conv_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()


async def update_conversation_title(conv_id: str, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now_iso(), conv_id)
        )
        await db.commit()


async def add_message(
    conv_id: str,
    role: str,
    content: str,
    tool_steps: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    msg_id = str(uuid.uuid4())
    ts = now_iso()
    steps_json = json.dumps(tool_steps) if tool_steps else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, tool_steps, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conv_id, role, content, steps_json, ts)
        )
        await db.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (ts, conv_id)
        )
        await db.commit()
    return {
        "id": msg_id,
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "tool_steps": tool_steps,
        "created_at": ts,
    }


async def get_messages(conv_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["tool_steps"] = json.loads(d["tool_steps"]) if d["tool_steps"] else None
                result.append(d)
            return result
