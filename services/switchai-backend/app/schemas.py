"""OpenAI-compatible request and response pydantic models.

These mirror the shape of the public OpenAI REST API so that any OpenAI SDK /
client pointed at this server's ``/v1`` base URL will "just work".
"""

from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatMessageIn(BaseModel):
    role: str
    content: Union[str, list[dict[str, Any]], None] = None
    name: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessageIn]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Union[str, dict[str, Any]]] = None
    response_format: Optional[dict[str, Any]] = None
    # OpenAI extras we accept-but-ignore (so SDKs don't error):
    top_p: Optional[float] = None
    n: Optional[int] = None
    stop: Optional[Union[str, list[str]]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    user: Optional[str] = None


class ChatMessageOut(BaseModel):
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatMessageOut
    finish_reason: Optional[str] = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: Usage = Field(default_factory=Usage)


# --- Streaming chunk shape (data: {...} SSE) ---


class ChatChunkDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[list[dict[str, Any]]] = None


class ChatChunkChoice(BaseModel):
    index: int = 0
    delta: ChatChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatChunkChoice]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class EmbeddingRequest(BaseModel):
    model: str
    input: Union[str, list[str]]
    # OpenAI extras accepted-but-ignored:
    encoding_format: Optional[str] = None
    dimensions: Optional[int] = None
    user: Optional[str] = None


class EmbeddingData(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingUsage(BaseModel):
    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage = Field(default_factory=EmbeddingUsage)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


class ImageRequest(BaseModel):
    model: str
    prompt: str
    n: int = 1
    size: Optional[str] = None
    response_format: Optional[str] = None
    user: Optional[str] = None


class ImageData(BaseModel):
    b64_json: Optional[str] = None
    url: Optional[str] = None


class ImageResponse(BaseModel):
    created: int
    data: list[ImageData]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ModelCard(BaseModel):
    id: str
    object: Literal["model"] = "model"
    owned_by: str
    created: int = 0


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelCard]


# ---------------------------------------------------------------------------
# Errors (OpenAI envelope)
# ---------------------------------------------------------------------------


class ErrorBody(BaseModel):
    message: str
    type: str = "invalid_request_error"
    code: Optional[int] = None
    param: Optional[str] = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
