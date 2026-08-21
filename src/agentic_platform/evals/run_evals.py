"""Automated evaluation harness for the agent team.

Runs each task in dataset.json through the full orchestrator and checks that
at least one of the expected phrases appears somewhere in the final answer or
the agent trace. This is intentionally simple (keyword grounding, not an
LLM-as-judge) so it runs deterministically and cheaply in CI; see README >
Roadmap for upgrading to LLM-judged rubrics.

Usage:
    python -m agentic_platform.evals.run_evals
"""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path

from ..agents.orchestrator import AgentTeam, run_task
from ..telemetry import configure_telemetry

_DATASET_PATH = Path(__file__).parent / "dataset.json"
_RESULTS_DIR = Path(__file__).parent.parent.parent.parent / "evals" / "results"


@dataclass
class EvalOutcome:
    case_id: str
    task: str
    passed: bool
    answer: str


def _load_dataset() -> list[dict]:
    return json.loads(_DATASET_PATH.read_text(encoding="utf-8"))


def _check(case: dict, answer: str, transcript_text: str) -> bool:
    haystack = f"{answer}\n{transcript_text}".lower()
    return any(phrase.lower() in haystack for phrase in case["must_include"])


async def main() -> int:
    configure_telemetry()
    dataset = _load_dataset()
    outcomes: list[EvalOutcome] = []

    async with AsyncExitStack() as stack:
        team = await AgentTeam.create(stack)

        for case in dataset:
            result = await run_task(team, case["task"])
            transcript_text = "\n".join(step.output for step in result.steps)
            passed = _check(case, result.final_answer, transcript_text)
            outcomes.append(EvalOutcome(case["id"], case["task"], passed, result.final_answer))

    _print_report(outcomes)
    _save_report(outcomes)

    return 0 if all(o.passed for o in outcomes) else 1


def _print_report(outcomes: list[EvalOutcome]) -> None:
    print("\n=== Eval Report ===")
    for o in outcomes:
        status = "PASS" if o.passed else "FAIL"
        print(f"[{status}] {o.case_id}: {o.task}")
        if not o.passed:
            print(f"       answer: {o.answer[:200]}")
    passed_count = sum(o.passed for o in outcomes)
    print(f"\n{passed_count}/{len(outcomes)} cases passed.")


def _save_report(outcomes: list[EvalOutcome]) -> None:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / "latest.json"
    out_path.write_text(
        json.dumps([o.__dict__ for o in outcomes], indent=2),
        encoding="utf-8",
    )
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
