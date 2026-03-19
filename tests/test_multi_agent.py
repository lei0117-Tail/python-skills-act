"""Unit tests for MultiAgent system."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills_executor.agent.multi_agent import (
    MultiAgent,
    SkillExecutionContext,
    SubAgent,
    SubAgentResult,
    build_multi_agent,
)
from skills_executor.providers.base import LLMResponse, ToolCallRequest
from skills_executor.skills.SkillsLoader import SkillsLoader
from skills_executor.tools.registry import ToolRegistry


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock()
    return provider


@pytest.fixture
def mock_tools():
    """Create a mock tool registry."""
    registry = ToolRegistry()
    # Mock tool definitions
    registry.get_definitions = MagicMock(return_value=[
        {
            "type": "function",
            "function": {
                "name": "exec",
                "description": "Execute shell command",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ])
    registry.execute = AsyncMock(return_value="Command executed successfully")
    return registry


@pytest.fixture
def mock_skills():
    """Create a mock skills loader."""
    skills = MagicMock(spec=SkillsLoader)
    skills.list_skills.return_value = [
        {"name": "weather", "path": "/path/to/weather/SKILL.md", "source": "workspace"},
        {"name": "csv-analysis", "path": "/path/to/csv/SKILL.md", "source": "workspace"},
    ]
    skills.build_skills_summary.return_value = """<skills>
  <skill available="true">
    <name>weather</name>
    <description>Get current weather</description>
    <location>/path/to/weather/SKILL.md</location>
  </skill>
</skills>"""
    skills.load_skill.return_value = """---
name: weather
description: Get weather
---

Use curl to get weather:
curl -s "wttr.in/Beijing?format=3"
"""
    skills._strip_frontmatter = lambda x: x.split("---\n")[-1].strip()
    return skills


class TestSkillIdentification:
    """Tests for skill identification mechanism."""

    @pytest.mark.asyncio
    async def test_identify_skill_match(self, mock_provider, mock_tools, mock_skills):
        """Test skill identification - match scenario."""
        # Setup provider to return "weather"
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="weather",
            finish_reason="stop",
        )

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
            model="test-model",
        )

        skill = await multi_agent._identify_skill("北京今天天气怎么样?")
        assert skill == "weather"

    @pytest.mark.asyncio
    async def test_identify_skill_no_match(self, mock_provider, mock_tools, mock_skills):
        """Test skill identification - no match scenario."""
        # Setup provider to return "NONE"
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="NONE",
            finish_reason="stop",
        )

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        skill = await multi_agent._identify_skill("1+1等于几?")
        assert skill is None

    @pytest.mark.asyncio
    async def test_identify_skill_invalid_name(self, mock_provider, mock_tools, mock_skills):
        """Test skill identification - invalid skill name."""
        # Setup provider to return non-existent skill
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="nonexistent",
            finish_reason="stop",
        )

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        skill = await multi_agent._identify_skill("some query")
        assert skill is None  # Should return None for non-existent skill


class TestSubAgentExecution:
    """Tests for SubAgent execution."""

    @pytest.mark.asyncio
    async def test_subagent_success(self, mock_provider, mock_tools):
        """Test SubAgent successful execution."""
        # Setup provider responses
        mock_provider.chat_with_retry.side_effect = [
            # First call: tool call
            LLMResponse(
                content="Checking weather...",
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="exec",
                        arguments={"command": "curl wttr.in/Beijing"},
                    )
                ],
                finish_reason="tool_calls",
            ),
            # Second call: final response
            LLMResponse(
                content="北京: ⛅️ +8°C",
                finish_reason="stop",
            ),
        ]

        execution_context = SkillExecutionContext(
            skill_name="weather",
            skill_content="Use curl to get weather",
            user_query="北京天气",
            workspace=Path.cwd(),
            model="test-model",
        )

        subagent = SubAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            execution_context=execution_context,
        )

        result = await subagent.execute()

        assert result.success is True
        assert result.content == "北京: ⛅️ +8°C"
        assert "exec" in result.tools_used
        assert result.error is None

    @pytest.mark.asyncio
    async def test_subagent_max_iterations(self, mock_provider, mock_tools):
        """Test SubAgent reaching max iterations."""
        # Setup provider to always return tool calls
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="Thinking...",
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="exec",
                    arguments={"command": "echo test"},
                )
            ],
            finish_reason="tool_calls",
        )

        execution_context = SkillExecutionContext(
            skill_name="test",
            skill_content="Test skill",
            user_query="test query",
            workspace=Path.cwd(),
            model="test-model",
            max_iterations=3,  # Low limit for testing
        )

        subagent = SubAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            execution_context=execution_context,
        )

        result = await subagent.execute()

        assert result.success is False
        assert "Max iterations" in result.error

    @pytest.mark.asyncio
    async def test_subagent_error_handling(self, mock_provider, mock_tools):
        """Test SubAgent error handling."""
        # Setup provider to return error
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="Error: API call failed",
            finish_reason="error",
        )

        execution_context = SkillExecutionContext(
            skill_name="test",
            skill_content="Test skill",
            user_query="test query",
            workspace=Path.cwd(),
            model="test-model",
        )

        subagent = SubAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            execution_context=execution_context,
        )

        result = await subagent.execute()

        assert result.success is False
        assert result.error is not None


class TestResultCompression:
    """Tests for result compression mechanism."""

    def test_compress_result(self, mock_provider, mock_tools, mock_skills):
        """Test result compression."""
        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        # Create a result with long content
        long_content = "a" * 2000
        result = SubAgentResult(
            skill_name="test",
            success=True,
            content=long_content,
            tools_used=["exec"],
        )

        multi_agent._record_subagent_result("test query", result)

        # Check compressed history
        assert len(multi_agent._history) == 2
        assistant_msg = multi_agent._history[-1]
        assert assistant_msg["role"] == "assistant"
        # Should be compressed to ~250 chars
        assert len(assistant_msg["content"]) <= 250
        assert "[Skill: test]" in assistant_msg["content"]


class TestMultiAgentIntegration:
    """Integration tests for MultiAgent."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_skill(self, mock_provider, mock_tools, mock_skills):
        """Test full workflow - using skill."""
        # Setup provider responses
        mock_provider.chat_with_retry.side_effect = [
            # Skill identification
            LLMResponse(content="weather", finish_reason="stop"),
            # SubAgent execution - tool call
            LLMResponse(
                content="Checking...",
                tool_calls=[
                    ToolCallRequest(id="call_1", name="exec", arguments={"command": "curl wttr.in"})
                ],
                finish_reason="tool_calls",
            ),
            # SubAgent execution - final
            LLMResponse(content="北京: ⛅️ +8°C", finish_reason="stop"),
        ]

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
            enable_subagent=True,
        )

        response, tools = await multi_agent.run("北京天气")

        assert response
        assert "exec" in tools
        # Check history is compressed
        assert len(multi_agent._history) == 2

    @pytest.mark.asyncio
    async def test_full_workflow_without_skill(self, mock_provider, mock_tools, mock_skills):
        """Test full workflow - without skill."""
        # Setup provider responses
        mock_provider.chat_with_retry.side_effect = [
            # Skill identification - no match
            LLMResponse(content="NONE", finish_reason="stop"),
            # Main agent response
            LLMResponse(content="1+1=2", finish_reason="stop"),
        ]

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        response, tools = await multi_agent.run("1+1等于几?")

        assert response == "1+1=2"
        assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_subagent_fallback(self, mock_provider, mock_tools, mock_skills):
        """Test SubAgent failure fallback to main agent."""
        # Setup provider responses
        mock_provider.chat_with_retry.side_effect = [
            # Skill identification
            LLMResponse(content="weather", finish_reason="stop"),
            # SubAgent execution - error
            LLMResponse(content="Error occurred", finish_reason="error"),
            # Main agent fallback
            LLMResponse(content="Fallback response", finish_reason="stop"),
        ]

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        response, tools = await multi_agent.run("北京天气")

        assert response == "Fallback response"


class TestMultiAgentStats:
    """Tests for MultiAgent statistics."""

    def test_get_stats(self, mock_provider, mock_tools, mock_skills):
        """Test get_stats method."""
        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
            enable_subagent=True,
        )

        stats = multi_agent.get_stats()

        assert "history_length" in stats
        assert "available_skills" in stats
        assert "subagent_enabled" in stats
        assert stats["subagent_enabled"] is True
        assert stats["history_length"] == 0
        assert stats["available_skills"] == 2


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_empty_query(self, mock_provider, mock_tools, mock_skills):
        """Test empty query handling."""
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="Please provide a query",
            finish_reason="stop",
        )

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        response, tools = await multi_agent.run("")

        assert response  # Should have a response

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_provider, mock_tools, mock_skills):
        """Test concurrent requests."""
        mock_provider.chat_with_retry.return_value = LLMResponse(
            content="Response",
            finish_reason="stop",
        )

        multi_agent = MultiAgent(
            provider=mock_provider,
            tool_registry=mock_tools,
            skills_loader=mock_skills,
            workspace=Path.cwd(),
        )

        # Run multiple requests concurrently
        tasks = [multi_agent.run(f"query {i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for response, tools in results:
            assert response
