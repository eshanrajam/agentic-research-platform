"""Magentic-style multi-agent orchestrator.

A lead "Orchestrator" agent repeatedly decides which specialist to invoke next
(Researcher, Coder, Analyst) given the running transcript, routes the draft
answer through a Critic once for a reflection pass, then returns a final,
reviewed answer. This mirrors the manager/specialist pattern popularized by
Microsoft's Magentic-One multi-agent research system, implemented here as an
explicit, testable loop on top of Microsoft Agent Framework agents and MCP
tool servers (rather than relying on unreleased/undocumented framework
internals) so behavior is transparent and easy to reason about in review.
"""
from __future__ import annotations

import json
import re
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from agent_framework import Agent, MCPStdioTool

from ..config import get_chat_client, settings
from .prompts import (
    ANALYST_PROMPT,
    CODER_PROMPT,
    CRITIC_PROMPT,
    ORCHESTRATOR_PROMPT,
    RESEARCHER_PROMPT,
)

_SPECIALIST_NAMES = {"Researcher", "Coder", "Analyst", "Critic"}


@dataclass
class Step:
    """One completed unit of work in an orchestration run, used for the trace UI and evals."""

    agent: str
    instruction: str
    output: str


@dataclass
class OrchestrationResult:
    final_answer: str
    steps: list[Step] = field(default_factory=list)
    truncated: bool = False


class AgentTeam:
    """Holds the live specialist Agent instances and their MCP tool connections.

    Construct via `AgentTeam.create(stack)` where `stack` is an `AsyncExitStack`
    owned by the caller (e.g. the FastAPI app lifespan) so every MCP subprocess
    and agent session is cleanly torn down together.
    """

    def __init__(self, agents: dict[str, Agent]):
        self.agents = agents

    @classmethod
    async def create(cls, stack: AsyncExitStack) -> AgentTeam:
        client = get_chat_client()

        web_tool = await stack.enter_async_context(
            MCPStdioTool(
                name="web_research",
                command=sys.executable,
                args=["-m", "agentic_platform.mcp_servers.web_search_server"],
            )
        )
        code_tool = await stack.enter_async_context(
            MCPStdioTool(
                name="code_exec",
                command=sys.executable,
                args=["-m", "agentic_platform.mcp_servers.code_exec_server"],
            )
        )
        kb_tool = await stack.enter_async_context(
            MCPStdioTool(
                name="knowledge_base",
                command=sys.executable,
                args=["-m", "agentic_platform.mcp_servers.knowledge_base_server"],
            )
        )

        agents = {
            "Orchestrator": await stack.enter_async_context(
                Agent(client=client, name="Orchestrator", instructions=ORCHESTRATOR_PROMPT)
            ),
            "Researcher": await stack.enter_async_context(
                Agent(client=client, name="Researcher", instructions=RESEARCHER_PROMPT, tools=web_tool)
            ),
            "Coder": await stack.enter_async_context(
                Agent(client=client, name="Coder", instructions=CODER_PROMPT, tools=code_tool)
            ),
            "Analyst": await stack.enter_async_context(
                Agent(client=client, name="Analyst", instructions=ANALYST_PROMPT, tools=kb_tool)
            ),
            "Critic": await stack.enter_async_context(Agent(client=client, name="Critic", instructions=CRITIC_PROMPT)),
        }
        return cls(agents)


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating stray prose or code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"expected a JSON object, got: {text!r}")
    return json.loads(match.group(0))


def _build_orchestrator_message(task: str, transcript: list[Step]) -> str:
    lines = [f"USER TASK: {task}", "", "TRANSCRIPT SO FAR:"]
    if not transcript:
        lines.append("(none yet - this is the first decision)")
    else:
        for i, step in enumerate(transcript, start=1):
            lines.append(f"{i}. [{step.agent}] instruction: {step.instruction}")
            lines.append(f"   output: {step.output}")
    lines.append("")
    lines.append("Decide the single next action now, as the required JSON object.")
    return "\n".join(lines)


async def _agent_text(agent: Agent, message: str) -> str:
    response = await agent.run(message)
    return getattr(response, "text", str(response))


async def run_task(team: AgentTeam, task: str) -> OrchestrationResult:
    """Run one orchestration loop for `task` and return the final, critic-reviewed answer."""
    transcript: list[Step] = []

    for _ in range(settings.max_orchestrator_steps):
        message = _build_orchestrator_message(task, transcript)
        raw_decision = await _agent_text(team.agents["Orchestrator"], message)

        try:
            decision = _extract_json(raw_decision)
            agent_name = str(decision.get("agent", "")).strip()
            instruction = str(decision.get("instruction", "")).strip()
        except (ValueError, json.JSONDecodeError):
            # The orchestrator failed to follow the JSON contract - treat its raw
            # text as a best-effort final answer rather than crashing the request.
            return OrchestrationResult(final_answer=raw_decision, steps=transcript, truncated=True)

        if agent_name == "FINAL":
            return OrchestrationResult(final_answer=instruction, steps=transcript)

        if agent_name not in _SPECIALIST_NAMES:
            transcript.append(
                Step(agent="Orchestrator", instruction=raw_decision, output=f"Unknown agent '{agent_name}', ignored.")
            )
            continue

        output = await _agent_text(team.agents[agent_name], instruction)
        transcript.append(Step(agent=agent_name, instruction=instruction, output=output))

    fallback = transcript[-1].output if transcript else "I was unable to complete this task in time."
    return OrchestrationResult(final_answer=fallback, steps=transcript, truncated=True)
