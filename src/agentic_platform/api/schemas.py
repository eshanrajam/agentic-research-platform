"""Request/response schemas for the chat API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class StepTrace(BaseModel):
    agent: str
    instruction: str
    output: str


class ChatResponse(BaseModel):
    answer: str
    steps: list[StepTrace]
    truncated: bool = False
