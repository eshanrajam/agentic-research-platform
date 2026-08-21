"""Centralized configuration and model-client factory.

Provider selection is model-agnostic: whichever of Azure OpenAI, Microsoft
Foundry, or OpenAI is configured via environment variables gets used, in that
priority order. This lets the same agent code run unchanged against any
backend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))

    azure_openai_api_key: str | None = field(default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY"))
    azure_openai_endpoint: str | None = field(default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT"))
    azure_openai_deployment: str | None = field(default_factory=lambda: os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"))
    azure_openai_embedding_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    )

    foundry_project_endpoint: str | None = field(default_factory=lambda: os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
    foundry_model: str | None = field(default_factory=lambda: os.getenv("FOUNDRY_MODEL"))

    tavily_api_key: str | None = field(default_factory=lambda: os.getenv("TAVILY_API_KEY"))

    chroma_persist_dir: str = field(default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"))
    enable_code_execution: bool = field(default_factory=lambda: _bool_env("ENABLE_CODE_EXECUTION", False))

    allowed_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
            if o.strip()
        ]
    )
    max_orchestrator_steps: int = field(default_factory=lambda: int(os.getenv("MAX_ORCHESTRATOR_STEPS", "8")))


settings = Settings()


def get_chat_client():
    """Return a chat client for whichever provider is configured.

    Priority: Azure OpenAI -> Microsoft Foundry -> OpenAI.
    """
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            model=settings.azure_openai_deployment,
        )

    if settings.foundry_project_endpoint and settings.foundry_model:
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import AzureCliCredential

        return FoundryChatClient(
            project_endpoint=settings.foundry_project_endpoint,
            model=settings.foundry_model,
            credential=AzureCliCredential(),
        )

    if settings.openai_api_key:
        from agent_framework.openai import OpenAIChatClient

        return OpenAIChatClient(api_key=settings.openai_api_key, model=settings.openai_model)

    raise RuntimeError(
        "No model provider configured. Set OPENAI_API_KEY, AZURE_OPENAI_* or FOUNDRY_* env vars (see .env.example)."
    )
