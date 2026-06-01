"""
DeepAgent — LangChain/LangGraph-based planning, orchestration, and re-evaluation
agent.

Architecture:
  1. PLANNING: LLM reviews the user's natural language query + available YAML
     skills → creates step-by-step plan
  2. EXECUTION: Executes each plan step by calling the corresponding skill
     function
  3. RE-EVALUATION: LLM reviews all collected results against the original query
     - If sufficient: return final analysis + chart data
     - If not & under max_iterations: re-plan with accumulated context
     - If max_iterations reached: synthesize best answer from collected results

Output:
  - research_note: the written analysis
  - charts: structured data for rendering charts
  - trace: step-by-step log designed for a non-technical reader
"""

import asyncio
import logging
import time
from typing import Any

import yaml

from server.api.properties.prompts.evaluate_prompt import EVALUATE_PROMPT_PATH
from server.api.properties.prompts.plan_prompt import PLAN_PROMPT_PATH
from server.api.properties.prompts.synthesis_prompt import SYNTHESIS_PROMPT_PATH
from server.api.properties.skills_loader import Skill, load_skills
from server.core.config import settings
from server.core.llm_factory import get_llm

logger = logging.getLogger(__name__)


def _build_skills_description(skills: dict[str, Skill]) -> str:
    """Build a human-readable description of available skills for the LLM."""
    parts = []
    for skill in skills.values():
        inputs_desc = ", ".join(
            (
                f"{name}: {info.get('type', 'unknown')}"
                f" ({'required' if info.get('required', True) else 'optional'})"
            )
            for name, info in skill.inputs.items()
        )
        parts.append(f"- {skill.name}: {skill.description}\n  Inputs: {inputs_desc}")
    return "\n".join(parts) if parts else "No skills available."


def _summarise_result(skill_name: str, result: Any) -> str:
    """Generate a short plain-English summary of a skill's result."""
    if result is None:
        return "No data returned."
    if isinstance(result, str):
        return result[:200]
    if isinstance(result, list):
        return f"Returned {skill_name} {len(result)} records."
    if isinstance(result, dict):
        # Try to extract meaningful summary
        keys = list(result.keys())
        summary_parts = []
        for key in keys[:3]:
            val = result[key]
            if isinstance(val, list):
                summary_parts.append(f"{key}: {len(val)} items")
            elif (
                isinstance(val, (int, float)) or isinstance(val, str) and len(val) < 100
            ):
                summary_parts.append(f"{key}: {val}")
        if summary_parts:
            return "; ".join(summary_parts)
        return f"Returned data with keys: {', '.join(keys[:5])}"
    return str(result)[:200]


# ---------------------------------------------------------------------------
# DeepAgent class
# ---------------------------------------------------------------------------


class DeepAgent:
    """Planning, orchestration, and re-evaluation agent using LangChain/LangGraph."""

    def __init__(
        self,
        skills: dict[str, Skill] | None = None,
        llm=None,
        max_iterations: int | None = None,
    ):
        self.skills = skills or load_skills()
        self.llm = llm or get_llm()
        self.max_iterations = max_iterations or settings.MAX_AGENT_ITERATIONS

    async def run(
        self,
        query: str,
        additional_context: str | None = None,
        on_trace_step: callable | None = None,
    ) -> dict:
        """Run the full DeepAgent loop: plan → execute → evaluate.

        Args:
            query: The user's natural language analysis request.
            additional_context: Optional context to guide the agent.
            on_trace_step: Optional async callback invoked after each trace step
                           is recorded. Receives the step dict as argument.

        Returns a dict with keys:
          - research_note: str — the written analysis
          - charts: list[dict] — chart-ready data series
          - trace: list[dict] — step-by-step log for non-technical readers
          - iterations: int — number of iterations completed
          - token_usage: dict — aggregated token counts across all LLM calls
        """
        skills_desc = _build_skills_description(self.skills)
        context = additional_context or "No additional context provided."

        # Collect all execution results and trace steps across iterations
        all_results = []
        trace_steps = []
        iteration = 0
        final_analysis = None
        final_charts = []

        # Accumulate token usage across all LLM calls
        token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        async def _emit_step(step: dict) -> None:
            """Append a trace step and notify the external callback.

            This is called both from _execute_plan (which already appends)
            and directly from run() for evaluation trace steps (which need
            appending). We always append here — _execute_plan also appends
            via _append_and_emit, so evaluation steps are covered too.
            """
            trace_steps.append(step)
            if on_trace_step:
                await on_trace_step(step)

        # --- ITERATION 1: Initial planning + execution ---
        plan, plan_tokens = await self._plan(skills_desc, query, context)
        token_usage["prompt_tokens"] += plan_tokens.get("prompt_tokens", 0)
        token_usage["completion_tokens"] += plan_tokens.get("completion_tokens", 0)
        token_usage["total_tokens"] += plan_tokens.get("total_tokens", 0)
        logger.info("Iteration 1: Plan produced with %d steps", len(plan))

        iteration_results, _ = await self._execute_plan(plan, trace_steps, _emit_step)
        all_results.extend(iteration_results)

        # Re-evaluate
        eval_result, eval_tokens = await self._evaluate(
            skills_desc, query, context, all_results
        )
        token_usage["prompt_tokens"] += eval_tokens.get("prompt_tokens", 0)
        token_usage["completion_tokens"] += eval_tokens.get("completion_tokens", 0)
        token_usage["total_tokens"] += eval_tokens.get("total_tokens", 0)
        iteration += 1

        if eval_result.get("sufficient"):
            logger.info("Evaluation passed after %d iteration(s)", iteration)
            final_analysis = eval_result.get("analysis", str(all_results))
            final_charts = eval_result.get("charts", [])
        else:
            # Record the evaluation as a trace step
            reason = eval_result.get("reason", "Results were insufficient")
            await _emit_step(
                {
                    "step_number": len(trace_steps) + 1,
                    "action": (
                        "Checked if the results so far are sufficient."
                        f" Decision: {reason}"
                    ),
                    "skill_used": "evaluation",
                    "input": {},
                    "output_summary": reason,
                    "status": "success",
                    "duration_seconds": None,
                }
            )

            # --- SUBSEQUENT ITERATIONS: Re-plan based on evaluation feedback ---
            while iteration < self.max_iterations and not final_analysis:
                logger.info(
                    "Evaluation: %s — re-planning (iteration %d/%d)",
                    reason,
                    iteration + 1,
                    self.max_iterations,
                )
                plan = self._convert_additional_steps(
                    eval_result.get("additional_steps", [])
                )
                if not plan:
                    logger.warning("No additional steps provided — breaking loop")
                    break

                iteration_results, _ = await self._execute_plan(
                    plan, trace_steps, _emit_step
                )
                all_results.extend(iteration_results)

                eval_result, eval_tokens = await self._evaluate(
                    skills_desc, query, context, all_results
                )
                token_usage["prompt_tokens"] += eval_tokens.get("prompt_tokens", 0)
                token_usage["completion_tokens"] += eval_tokens.get("completion_tokens", 0)
                token_usage["total_tokens"] += eval_tokens.get("total_tokens", 0)
                iteration += 1

                if eval_result.get("sufficient"):
                    final_analysis = eval_result.get("analysis", str(all_results))
                    final_charts = eval_result.get("charts", [])
                    break

                # Record re-evaluation as trace step
                reason = eval_result.get("reason", "Results were still insufficient")
                await _emit_step(
                    {
                        "step_number": len(trace_steps) + 1,
                        "action": (
                            "Re-checked if the results are sufficient."
                            f" Decision: {reason}"
                        ),
                        "skill_used": "evaluation",
                        "input": {},
                        "output_summary": reason,
                        "status": "success",
                        "duration_seconds": None,
                    }
                )

            # If still not sufficient, synthesize from collected data
            if not final_analysis:
                logger.info("Max iterations reached — synthesising from collected data")
                synthesis_result, synth_tokens = await self._synthesize(
                    query, context, all_results
                )
                token_usage["prompt_tokens"] += synth_tokens.get("prompt_tokens", 0)
                token_usage["completion_tokens"] += synth_tokens.get("completion_tokens", 0)
                token_usage["total_tokens"] += synth_tokens.get("total_tokens", 0)
                final_analysis = synthesis_result.get("analysis", str(all_results))
                final_charts = synthesis_result.get("charts", [])

        return {
            "research_note": final_analysis or "No analysis could be produced.",
            "charts": final_charts,
            "trace": trace_steps,
            "iterations": iteration,
            "token_usage": token_usage,
        }

    async def _plan(
        self,
        skills_desc: str,
        query: str,
        additional_context: str,
    ) -> tuple[list[dict], dict]:
        """Step 1: LLM creates a plan using available skills.

        Returns (plan_steps, token_usage_dict).
        """
        prompt = PLAN_PROMPT_PATH.format(
            skills_description=skills_desc,
            query=query,
            additional_context=additional_context,
        )
        response = await self.llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        plan = self._parse_json_list(content)
        tokens = self._extract_token_usage(response)
        return plan, tokens

    async def _execute_plan(
        self,
        plan: list[dict],
        existing_traces: list[dict],
        emit_step: callable | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Step 2: Execute each element in the plan by calling skill functions.

        Each element in the plan is either:
          - A single step dict with keys: "skill", "params", "reason"
          - A parallel group dict with key "parallel" containing a list of step dicts

        Single steps execute sequentially. All steps in a parallel group execute
        concurrently via asyncio.gather().

        Args:
            plan: List of plan elements (steps or parallel groups) to execute.
            existing_traces: List to which trace steps are appended (by emit_step).
            emit_step: Optional async callback that receives the trace step dict.
                       It is responsible for appending to existing_traces.

        Returns (results, updated_traces).
        """
        results = []
        step_offset = len(existing_traces)

        async def _call_emit(step: dict) -> None:
            """Call external callback (which handles appending to existing_traces)."""
            if emit_step:
                await emit_step(step)

        for idx, entry in enumerate(plan):
            if "parallel" in entry:
                # Run all steps in this group concurrently
                parallel_steps = entry["parallel"]
                group_results = await asyncio.gather(
                    *[
                        self._execute_single_step(
                            step=step,
                            step_number=step_offset + idx + 1,
                            call_emit=_call_emit,
                        )
                        for step in parallel_steps
                    ]
                )
                results.extend(group_results)
            else:
                # Single step — execute sequentially
                result = await self._execute_single_step(
                    step=entry,
                    step_number=step_offset + idx + 1,
                    call_emit=_call_emit,
                )
                results.append(result)

        return results, existing_traces

    async def _execute_single_step(
        self,
        step: dict,
        step_number: int,
        call_emit: callable,
    ) -> dict:
        """Execute a single plan step by calling the corresponding skill function.

        Args:
            step: A dict with keys "skill", "params", "reason".
            step_number: The step number for trace logging.
            call_emit: Async callback to emit a trace step.

        Returns a result dict with keys "skill", "reason", "status", etc.
        """
        skill_name = step.get("skill")
        params = step.get("params", {})
        reason = step.get("reason", "")
        start_time = time.time()

        skill = self.skills.get(skill_name)
        if not skill:
            logger.warning("Skill '%s' not found — skipping", skill_name)
            elapsed = time.time() - start_time
            result = {
                "skill": skill_name,
                "reason": reason,
                "status": "error",
                "error": f"Skill '{skill_name}' not found",
            }
            await call_emit(
                {
                    "step_number": step_number,
                    "action": reason
                    or f"Tried to call skill '{skill_name}' but it was not found",
                    "skill_used": skill_name,
                    "input": params,
                    "output_summary": (
                        f"Skill '{skill_name}' is not available."
                        " Cannot proceed with this step."
                    ),
                    "status": "error",
                    "duration_seconds": round(elapsed, 2),
                }
            )
            return result

        try:
            logger.info("Executing skill '%s' with params: %s", skill_name, params)
            start_time = time.time()
            skill_result = await skill.call(**params)
            elapsed = time.time() - start_time
            summary = _summarise_result(skill_name, skill_result)
            result = {
                "skill": skill_name,
                "reason": reason,
                "status": "success",
                "result": skill_result,
            }
            await call_emit(
                {
                    "step_number": step_number,
                    "action": reason or f"Ran the '{skill_name}' skill",
                    "skill_used": skill_name,
                    "input": params,
                    "output_summary": summary,
                    "status": "success",
                    "duration_seconds": round(elapsed, 2),
                }
            )
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception("Skill '%s' failed: %s", skill_name, e)
            result = {
                "skill": skill_name,
                "reason": reason,
                "status": "error",
                "error": str(e),
            }
            await call_emit(
                {
                    "step_number": step_number,
                    "action": reason or f"Tried to run the '{skill_name}' skill",
                    "skill_used": skill_name,
                    "input": params,
                    "output_summary": f"Failed: {str(e)}",
                    "status": "error",
                    "duration_seconds": round(elapsed, 2),
                }
            )
            return result

    async def _evaluate(
        self,
        skills_desc: str,
        query: str,
        additional_context: str,
        all_results: list[dict],
    ) -> tuple[dict, dict]:
        """Step 3: LLM evaluates whether results are sufficient.

        Returns (evaluation_result_dict, token_usage_dict).
        """
        execution_results_str = yaml.dump(all_results, default_flow_style=False)
        prompt = EVALUATE_PROMPT_PATH.format(
            skills_description=skills_desc,
            query=query,
            additional_context=additional_context,
            execution_results=execution_results_str,
        )
        response = await self.llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        result = self._parse_json_obj(content)
        tokens = self._extract_token_usage(response)
        return result, tokens

    async def _synthesize(
        self,
        query: str,
        additional_context: str,
        all_results: list[dict],
    ) -> tuple[dict, dict]:
        """Final synthesis when max iterations reached without sufficient evaluation.

        Returns (synthesis_result_dict, token_usage_dict).
        """
        execution_results_str = yaml.dump(all_results, default_flow_style=False)
        prompt = SYNTHESIS_PROMPT_PATH.format(
            query=query,
            additional_context=additional_context,
            execution_results=execution_results_str,
        )
        response = await self.llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        result = self._parse_json_obj(content)
        tokens = self._extract_token_usage(response)
        return result, tokens

    @staticmethod
    def _extract_token_usage(response) -> dict:
        """Extract token usage from an LLM response, handling various providers.

        Checks in order:
          1. ``usage_metadata`` — standardised LangChain attribute on AIMessage
          2. ``response_metadata['token_usage']`` — OpenAI-provider format
          3. ``response_metadata['usage']`` — Anthropic-provider format

        Returns a dict with keys ``prompt_tokens``, ``completion_tokens``,
        ``total_tokens`` (defaults to 0 for each if no data is available).
        """
        # LangChain's standardised usage_metadata attribute
        usage = getattr(response, "usage_metadata", None)
        if usage and isinstance(usage, dict):
            return {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

        # Fallback: provider-specific response_metadata
        meta = getattr(response, "response_metadata", None) or {}

        # OpenAI format: meta["token_usage"]
        token_usage = meta.get("token_usage")
        if token_usage and isinstance(token_usage, dict):
            prompt = token_usage.get("prompt_tokens", 0)
            completion = token_usage.get("completion_tokens", 0)
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            }

        # Anthropic format: meta["usage"]
        usage = meta.get("usage")
        if usage and isinstance(usage, dict):
            prompt = usage.get("input_tokens", 0)
            completion = usage.get("output_tokens", 0)
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            }

        # No token data available (e.g. local Ollama models)
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _parse_json_list(self, content: str) -> list[dict]:
        """Try to parse LLM output as a JSON list, with error handling."""
        import json

        content = content.strip()
        # Try to extract JSON from markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            logger.warning("Parsed JSON was not a list: %s", type(result))
            return []
        except json.JSONDecodeError as e:
            logger.exception(
                "Failed to parse LLM output as JSON: %s\nContent: %s", e, content[:200]
            )
            return []

    def _parse_json_obj(self, content: str) -> dict:
        """Try to parse LLM output as a JSON object, with error handling."""
        import json

        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
            logger.warning("Parsed JSON was not a dict: %s", type(result))
            return {"sufficient": True, "analysis": str(content), "charts": []}
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM output as JSON obj: %s", content[:200])
            return {"sufficient": True, "analysis": content, "charts": []}

    @staticmethod
    def _convert_additional_steps(steps: list) -> list[dict]:
        """Convert evaluation 'additional_steps' back to plan format.

        Preserves both single steps and parallel group structures
        (dicts with a "parallel" key).
        """
        if not steps:
            return []
        result = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            # If this is a parallel group, pass it through as-is
            if "parallel" in step:
                result.append(step)
            else:
                result.append(
                    {
                        "skill": step.get("skill", ""),
                        "params": step.get("params", {}),
                        "reason": step.get("reason", ""),
                    }
                )
        return result
