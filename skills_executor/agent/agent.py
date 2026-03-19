"""Agent loop — drives the LLM ↔ tool-call cycle."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger

from skills_executor.agent.context import ContextBuilder
from skills_executor.providers.base import LLMProvider, LLMResponse
from skills_executor.providers.custom_provider import CustomProvider
from skills_executor.skills.SkillsLoader import SkillsLoader
from skills_executor.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from skills_executor.tools.registry import ToolRegistry
from skills_executor.tools.shell import ExecTool

# ── defaults ────────────────────────────────────────────────────────────────

_DEFAULT_MODEL = "glm-5"
_DEFAULT_MAX_ITERATIONS = 30
_DEFAULT_WORKSPACE = Path("~/").expanduser()

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>")


def _strip_think(text: str | None) -> str | None:
    """Remove <think>…</think> blocks that some models embed in content."""
    if not text:
        return None
    return _THINK_RE.sub("", text).strip() or None


# ── Agent class ──────────────────────────────────────────────────────────────

class Agent:
    """
    Stateful agent that drives the LLM ↔ tool-call loop.

    Each instance owns its own message history so multiple concurrent
    conversations don't share state.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        context_builder: ContextBuilder,
        model: str = _DEFAULT_MODEL,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self.provider = provider
        self.tools = tool_registry
        self.context = context_builder
        self.model = model
        self.max_iterations = max_iterations

        # Cache tool definitions — they don't change after registration
        self._tool_defs: list[dict[str, Any]] = tool_registry.get_definitions()

        # Per-conversation message history (excludes system prompt)
        self._history: list[dict[str, Any]] = []

        # Running count of consecutive tool errors for early-exit guard
        self._consecutive_tool_errors: int = 0
        self._MAX_CONSECUTIVE_ERRORS = 3

    # ── public API ────────────────────────────────────────────────────────

    async def run(self, user_message: str) -> tuple[str, list[str]]:
        """
        Process a user message through the agent loop.

        Returns:
            (final_text, tools_used_list)
        """
        self._consecutive_tool_errors = 0
        final_content, tools_used = await self._loop(user_message)
        return final_content, tools_used

    def reset_history(self) -> None:
        """Clear conversation history (start a new conversation)."""
        self._history.clear()

    # ── core loop ─────────────────────────────────────────────────────────

    async def _loop(self, user_message: str) -> tuple[str, list[str]]:
        """Inner agent loop — returns (final_text, tools_used)."""
        tools_used: list[str] = []
        final_content: str | None = None

        # Build the full message list for this turn
        messages = self.context.build_messages(self._history, user_message)

        for iteration in range(1, self.max_iterations + 1):
            logger.debug("Agent iteration {}/{}", iteration, self.max_iterations)

            response: LLMResponse = await self.provider.chat_with_retry(
                messages=messages,
                tools=self._tool_defs,
                model=self.model,
            )

            # ── terminal states ──────────────────────────────────────────
            if response.finish_reason == "error":
                clean = _strip_think(response.content)
                logger.error("LLM returned error: {}", (clean or "")[:200])
                final_content = clean or "Sorry, I encountered an error calling the AI model."
                break

            if response.finish_reason == "length":
                logger.warning("LLM hit max-token limit at iteration {}", iteration)
                final_content = (
                    response.content or
                    "The response was cut off because it exceeded the token limit. "
                    "Try breaking your request into smaller pieces."
                )
                break

            # ── tool calls ───────────────────────────────────────────────
            if response.has_tool_calls:
                tool_call_dicts = [tc.to_openai_tool_call() for tc in response.tool_calls]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])

                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    logger.debug("Tool result: {}", result[:300])

                    # Track consecutive errors for early exit
                    if result.startswith("Error"):
                        self._consecutive_tool_errors += 1
                        if self._consecutive_tool_errors >= self._MAX_CONSECUTIVE_ERRORS:
                            logger.error(
                                "Aborting: {} consecutive tool errors", self._consecutive_tool_errors
                            )
                            final_content = (
                                f"Stopped after {self._consecutive_tool_errors} consecutive tool errors. "
                                "Last error: " + result
                            )
                            return final_content, tools_used
                    else:
                        self._consecutive_tool_errors = 0

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

            # ── final text response ──────────────────────────────────────
            else:
                clean = _strip_think(response.content)
                messages = self.context.add_assistant_message(
                    messages, clean,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        # ── max iterations guard ─────────────────────────────────────────
        if final_content is None:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. Try breaking the task into smaller steps."
            )

        # Persist this turn into history (skip the system message at index 0)
        self._history = messages[1:]
        return final_content, tools_used


# ── factory helper ────────────────────────────────────────────────────────────

def build_default_agent(
    skill_folder: str = "~/.claude/skills",
    workspace: Path | None = None,
    model: str = _DEFAULT_MODEL,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
) -> Agent:
    """
    Construct a ready-to-use Agent with the default tool set and provider.

    Keeps wiring logic out of the module top-level so it only runs when
    explicitly requested (no surprise side-effects on import).
    """
    # Load .env file before creating provider
    load_dotenv()

    ws = workspace or _DEFAULT_WORKSPACE
    allowed = ws

    skills_loader = SkillsLoader(skill_folder)

    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace=ws, allowed_dir=allowed, extra_allowed_dirs=[allowed]))
    for cls in (WriteFileTool, EditFileTool, ListDirTool):
        registry.register(cls(workspace=ws, allowed_dir=allowed))
    registry.register(ExecTool())

    provider = CustomProvider()
    ctx = ContextBuilder(skills_loader)

    return Agent(
        provider=provider,
        tool_registry=registry,
        context_builder=ctx,
        model=model,
        max_iterations=max_iterations,
    )


# ── manual smoke-test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main() -> None:
        agent = build_default_agent()
        reply, used = await agent.run("帮我获取一下北京今天的天气")
        print("Reply:", reply)
        print("Tools used:", used)

    asyncio.run(_main())

