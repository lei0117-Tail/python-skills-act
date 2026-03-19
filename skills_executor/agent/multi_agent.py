"""MultiAgent system with SubAgent delegation for skill execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from skills_executor.agent.agent import Agent
from skills_executor.agent.context import ContextBuilder
from skills_executor.providers.base import LLMProvider
from skills_executor.skills.SkillsLoader import SkillsLoader
from skills_executor.tools.registry import ToolRegistry


@dataclass
class SubAgentResult:
    """Result from a SubAgent execution."""

    skill_name: str
    success: bool
    content: str
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class SkillExecutionContext:
    """Context for executing a skill in a SubAgent."""

    skill_name: str
    skill_content: str
    user_query: str
    workspace: Path
    model: str
    max_iterations: int = 10  # SubAgent 使用更少的迭代次数


class SubAgent:
    """
    Lightweight agent for executing a single skill in isolation.

    SubAgent has its own context and history, preventing skill execution
    from polluting the main agent's context window.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        execution_context: SkillExecutionContext,
    ) -> None:
        self.provider = provider
        self.tools = tool_registry
        self.context_data = execution_context

        # Build a minimal context builder with only this skill
        self._build_context()

    def _build_context(self) -> None:
        """Build a minimal system prompt with only the target skill."""
        skill_instruction = f"""# Skill Execution Mode

You are executing the **{self.context_data.skill_name}** skill.

## Skill Instructions
{self.context_data.skill_content}

## User Query
{self.context_data.user_query}

## Guidelines
- Follow the skill instructions precisely
- Use available tools to complete the task
- Return a concise result focused on the user query
- Do NOT mention that you are a SubAgent or in skill execution mode
"""
        self.system_prompt = skill_instruction

    async def execute(self) -> SubAgentResult:
        """Execute the skill and return the result."""
        logger.info(f"SubAgent executing skill: {self.context_data.skill_name}")

        tools_used: list[str] = []
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.context_data.user_query},
        ]

        try:
            # Simple loop (no history accumulation)
            for iteration in range(1, self.context_data.max_iterations + 1):
                logger.debug(f"SubAgent iteration {iteration}/{self.context_data.max_iterations}")

                response = await self.provider.chat_with_retry(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.context_data.model,
                    max_tokens=2048,  # SubAgent 使用更少的 token
                    temperature=0.7,
                )

                # Handle errors
                if response.finish_reason == "error":
                    return SubAgentResult(
                        skill_name=self.context_data.skill_name,
                        success=False,
                        content="",
                        error=response.content or "Unknown error",
                    )

                # Handle tool calls
                if response.has_tool_calls:
                    tool_call_dicts = [tc.to_openai_tool_call() for tc in response.tool_calls]
                    messages.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": tool_call_dicts,
                    })

                    for tool_call in response.tool_calls:
                        tools_used.append(tool_call.name)
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })

                # Got final response
                else:
                    return SubAgentResult(
                        skill_name=self.context_data.skill_name,
                        success=True,
                        content=response.content or "",
                        tools_used=tools_used,
                        token_usage=response.usage,
                    )

            # Max iterations reached
            return SubAgentResult(
                skill_name=self.context_data.skill_name,
                success=False,
                content="",
                error=f"Max iterations ({self.context_data.max_iterations}) reached",
            )

        except Exception as e:
            logger.error(f"SubAgent execution failed: {e}")
            return SubAgentResult(
                skill_name=self.context_data.skill_name,
                success=False,
                content="",
                error=str(e),
            )


class MultiAgent:
    """
    Multi-agent orchestrator that delegates skill execution to SubAgents.

    The main agent maintains a lightweight context with only skill summaries.
    When a skill needs to be executed, it spawns a SubAgent with isolated
    context, preventing context pollution and reducing token usage.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        skills_loader: SkillsLoader,
        workspace: Path,
        model: str = "glm-5",
        max_iterations: int = 30,
        enable_subagent: bool = True,
    ) -> None:
        self.provider = provider
        self.tools = tool_registry
        self.skills = skills_loader
        self.workspace = workspace
        self.model = model
        self.max_iterations = max_iterations
        self.enable_subagent = enable_subagent

        # Build main context (lightweight, only skill summaries)
        self.context = ContextBuilder(skills_loader)

        # Main agent history
        self._history: list[dict[str, Any]] = []

    async def run(self, user_message: str) -> tuple[str, list[str]]:
        """
        Process a user message.

        The main agent decides whether to:
        1. Execute a skill via SubAgent (if skill is identified)
        2. Handle the query directly (if no skill needed)

        Returns:
            (final_text, tools_used_list)
        """
        # Step 1: Check if user query matches a skill
        skill_match = await self._identify_skill(user_message)

        if skill_match and self.enable_subagent:
            # Step 2: Delegate to SubAgent
            logger.info(f"Delegating to SubAgent for skill: {skill_match}")
            # 多skill 是不是可以并行处理
            result = await self._execute_skill_via_subagent(skill_match, user_message)

            if result.success:
                # Record the result in main agent history (compressed)
                self._record_subagent_result(user_message, result)
                return result.content, result.tools_used
            else:
                # Fallback to main agent if SubAgent fails
                logger.warning(f"SubAgent failed: {result.error}, falling back to main agent")
                return await self._run_main_agent(user_message)

        # Step 3: No skill match, use main agent
        return await self._run_main_agent(user_message)

    async def _identify_skill(self, user_message: str) -> str | None:
        """
        Identify if the user query matches a skill.

        Uses a lightweight LLM call with only skill summaries.
        """
        skills_summary = self.skills.build_skills_summary()
        if not skills_summary:
            return None

        identification_prompt = f"""Given the user query and available skills, identify if a skill should be used.

Available skills:
{skills_summary}

User query: {user_message}

If a skill matches, respond with ONLY the skill name (e.g., "weather").
If no skill matches, respond with "NONE".
"""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You are a skill identifier. Respond with skill name or NONE."},
                    {"role": "user", "content": identification_prompt},
                ],
                model=self.model,
                max_tokens=50,
                temperature=0.0,
            )

            skill_name = (response.content or "").strip()

            # Validate the skill exists
            if skill_name and skill_name != "NONE":
                available_skills = [s["name"] for s in self.skills.list_skills()]
                if skill_name in available_skills:
                    return skill_name

            return None

        except Exception as e:
            logger.warning(f"Skill identification failed: {e}")
            return None

    async def _execute_skill_via_subagent(
        self,
        skill_name: str,
        user_query: str,
    ) -> SubAgentResult:
        """Execute a skill in an isolated SubAgent."""
        # Load full skill content
        skill_content = self.skills.load_skill(skill_name)
        if not skill_content:
            return SubAgentResult(
                skill_name=skill_name,
                success=False,
                content="",
                error=f"Skill '{skill_name}' not found",
            )

        # Strip frontmatter
        skill_content = self.skills._strip_frontmatter(skill_content)

        # Create execution context
        execution_context = SkillExecutionContext(
            skill_name=skill_name,
            skill_content=skill_content,
            user_query=user_query,
            workspace=self.workspace,
            model=self.model,
            max_iterations=10,  # SubAgent 使用更少的迭代
        )

        # Create and execute SubAgent
        subagent = SubAgent(
            provider=self.provider,
            tool_registry=self.tools,
            execution_context=execution_context,
        )

        return await subagent.execute()

    async def _run_main_agent(self, user_message: str) -> tuple[str, list[str]]:
        """Run the main agent loop (fallback when no skill is used)."""
        # Create a temporary Agent instance
        agent = Agent(
            provider=self.provider,
            tool_registry=self.tools,
            context_builder=self.context,
            model=self.model,
            max_iterations=self.max_iterations,
        )

        # Restore history
        agent._history = self._history.copy()

        # Run the agent
        final_content, tools_used = await agent.run(user_message)

        # Save history
        self._history = agent._history

        return final_content, tools_used

    def _record_subagent_result(self, user_query: str, result: SubAgentResult) -> None:
        """
        Record SubAgent result in main agent history (compressed format).

        This keeps the main agent aware of what happened without including
        the full skill content and tool call details.
        """
        compressed_result = (
            f"[Skill: {result.skill_name}] "
            f"{result.content[:200]}..."  # Only keep first 200 chars
        )

        self._history.append({"role": "user", "content": user_query})
        self._history.append({"role": "assistant", "content": compressed_result})

    def reset_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the multi-agent system."""
        return {
            "history_length": len(self._history),
            "available_skills": len(self.skills.list_skills()),
            "subagent_enabled": self.enable_subagent,
        }


# ── Factory helper ────────────────────────────────────────────────────────────

def build_multi_agent(
    provider: LLMProvider,
    tool_registry: ToolRegistry,
    skills_loader: SkillsLoader,
    workspace: Path,
    model: str = "glm-5",
    max_iterations: int = 30,
    enable_subagent: bool = True,
) -> MultiAgent:
    """
    Build a MultiAgent instance.

    Args:
        provider: LLM provider
        tool_registry: Tool registry
        skills_loader: Skills loader
        workspace: Working directory
        model: Model name
        max_iterations: Max iterations for main agent
        enable_subagent: Enable SubAgent delegation (set False to use main agent only)

    Returns:
        MultiAgent instance
    """
    return MultiAgent(
        provider=provider,
        tool_registry=tool_registry,
        skills_loader=skills_loader,
        workspace=workspace,
        model=model,
        max_iterations=max_iterations,
        enable_subagent=enable_subagent,
    )
