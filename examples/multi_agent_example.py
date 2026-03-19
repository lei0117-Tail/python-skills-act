"""Example: Using MultiAgent with SubAgent delegation."""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from skills_executor.agent.multi_agent import build_multi_agent
from skills_executor.providers.custom_provider import CustomProvider
from skills_executor.skills.SkillsLoader import SkillsLoader
from skills_executor.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from skills_executor.tools.registry import ToolRegistry
from skills_executor.tools.shell import ExecTool


async def main():
    """Demonstrate MultiAgent with SubAgent delegation."""
    # Load environment
    load_dotenv()

    # Setup
    workspace = Path("~/.").expanduser()
    skills_loader = SkillsLoader("~/.claude/skills")

    # Register tools
    registry = ToolRegistry()
    registry.register(ReadFileTool(workspace=workspace, allowed_dir=workspace, extra_allowed_dirs=[workspace]))
    for cls in (WriteFileTool, EditFileTool, ListDirTool):
        registry.register(cls(workspace=workspace, allowed_dir=workspace))
    registry.register(ExecTool())

    # Create provider
    provider = CustomProvider()

    # Build MultiAgent
    multi_agent = build_multi_agent(
        provider=provider,
        tool_registry=registry,
        skills_loader=skills_loader,
        workspace=workspace,
        model="glm-5",
        enable_subagent=True,  # Enable SubAgent delegation
    )

    print("=" * 60)
    print("MultiAgent Demo - SubAgent Delegation")
    print("=" * 60)

    # Example 1: Query that matches a skill (will use SubAgent)
    print("\n[Example 1] Query with skill match (weather)")
    print("-" * 60)
    query1 = "北京今天天气怎么样?"
    response1, tools1 = await multi_agent.run(query1)
    print(f"Query: {query1}")
    print(f"Response: {response1}")
    print(f"Tools used: {tools1}")

    # Example 2: Query without skill match (will use main agent)
    print("\n[Example 2] Query without skill match")
    print("-" * 60)
    query2 = "1+1等于几?"
    response2, tools2 = await multi_agent.run(query2)
    print(f"Query: {query2}")
    print(f"Response: {response2}")
    print(f"Tools used: {tools2}")

    # Example 3: Check stats
    print("\n[Stats]")
    print("-" * 60)
    stats = multi_agent.get_stats()
    print(f"History length: {stats['history_length']}")
    print(f"Available skills: {stats['available_skills']}")
    print(f"SubAgent enabled: {stats['subagent_enabled']}")

    # Example 4: Compare with SubAgent disabled
    print("\n[Example 4] Same query with SubAgent disabled")
    print("-" * 60)
    multi_agent_no_sub = build_multi_agent(
        provider=provider,
        tool_registry=registry,
        skills_loader=skills_loader,
        workspace=workspace,
        model="glm-5",
        enable_subagent=False,  # Disable SubAgent
    )
    response3, tools3 = await multi_agent_no_sub.run(query1)
    print(f"Query: {query1}")
    print(f"Response: {response3}")
    print(f"Tools used: {tools3}")


if __name__ == "__main__":
    asyncio.run(main())
