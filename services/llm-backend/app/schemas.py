"""OpenAI-compatible request/response Pydantic models."""
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ── Chat completions ────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    n: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    user: Optional[str] = None
    seed: Optional[int] = None
    # Extra fields are tolerated and forwarded — LiteLLM `drop_params` strips
    # what individual providers don't support.
    model_config = {"extra": "allow"}


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: ChatUsage = Field(default_factory=ChatUsage)


# ── Embeddings ──────────────────────────────────────────────────────────


class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, List[str]]
    user: Optional[str] = None
    encoding_format: Optional[str] = None
    dimensions: Optional[int] = None


class EmbeddingItem(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: List[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[EmbeddingItem]
    model: str
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)


# ── Models listing ─────────────────────────────────────────────────────


class ModelInfo(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "litellm"


class ModelsListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[ModelInfo]


# ── Error envelope (OpenAI-compatible) ─────────────────────────────────


class ErrorBody(BaseModel):
    message: str
    type: str = "invalid_request_error"
    code: Optional[int] = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
