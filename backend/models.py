from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    model: str = "mock"
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    model: str = "mock"


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    tool_steps: Optional[List[Dict[str, Any]]] = None
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    model: str
    created_at: str
    updated_at: str


class SettingsUpdate(BaseModel):
    provider: str = "ollama"
    model: str = "llama3.2"
    api_key: Optional[str] = None
    base_url: Optional[str] = "http://localhost:11434/v1"
