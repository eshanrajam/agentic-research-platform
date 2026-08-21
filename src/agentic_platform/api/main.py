"""FastAPI entrypoint: exposes the multi-agent orchestrator over HTTP and serves the demo web UI."""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..agents.orchestrator import AgentTeam, run_task
from ..config import settings
from ..telemetry import configure_telemetry
from .schemas import ChatRequest, ChatResponse, StepTrace

logger = logging.getLogger(__name__)

_stack: AsyncExitStack | None = None
_team: AgentTeam | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _stack, _team
    configure_telemetry()
    _stack = AsyncExitStack()
    try:
        _team = await AgentTeam.create(_stack)
        logger.info("Agent team initialized: %s", ", ".join(_team.agents))
    except Exception:
        logger.exception("Failed to initialize agent team - is a model provider configured in .env?")
        _team = None
    yield
    if _stack is not None:
        await _stack.aclose()


app = FastAPI(title="Agentic Research Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent_team_ready": _team is not None}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if _team is None:
        raise HTTPException(status_code=503, detail="Agent team is not initialized. Check server configuration.")
    try:
        result = await run_task(_team, req.message)
    except Exception:
        logger.exception("Orchestration run failed")
        raise HTTPException(status_code=500, detail="The agent team failed to complete this request.") from None

    return ChatResponse(
        answer=result.final_answer,
        steps=[StepTrace(agent=s.agent, instruction=s.instruction, output=s.output) for s in result.steps],
        truncated=result.truncated,
    )


app.mount("/", StaticFiles(directory="web", html=True), name="web")
