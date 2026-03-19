"""CLI entry point for skills-executor."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from dotenv import load_dotenv

from skills_executor.agent.agent import build_default_agent

app = typer.Typer(
    name="python-skill-bot",
    help="AI agent with skill execution capabilities",
    add_completion=False,
)

console = Console()


@app.command()
def run(
    message: Annotated[
        str,
        typer.Option("-m", "--message", help="The message to send to the agent"),
    ],
    skill_folder: Annotated[
        str,
        typer.Option("-s", "--skill-folder", help="Path to skills directory"),
    ] = "~/.claude/skills",
    workspace: Annotated[
        str,
        typer.Option("-w", "--workspace", help="Workspace directory"),
    ] = "~",
    model: Annotated[
        str,
        typer.Option("--model", help="LLM model to use"),
    ] = "glm-5",
    max_iterations: Annotated[
        int,
        typer.Option("--max-iterations", help="Maximum tool call iterations"),
    ] = 30,
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Enable verbose logging"),
    ] = False,
) -> None:
    """
    Run the AI agent with the given message.

    Example:
        python-skill-bot -m "帮我获取北京今天的天气"
    """
    # Load .env file before running
    load_dotenv()

    # Configure logging
    if verbose:
        logger.add(
            lambda msg: console.print(f"[dim]{msg}[/dim]"),
            format="{time:HH:mm:ss} | {level:<8} | {message}",
            level="DEBUG",
        )
    else:
        logger.remove()  # Disable default handler
        logger.add(
            lambda msg: None,  # Silent handler
            level="INFO",
        )

    ws = Path(workspace).expanduser()

    console.print(Panel.fit(
        f"[bold blue]Python Skill Bot[/bold blue]\n"
        f"[dim]Model: {model} | Workspace: {ws}[/dim]",
        border_style="blue",
    ))

    async def _run() -> None:
        agent = build_default_agent(
            skill_folder=skill_folder,
            workspace=ws,
            model=model,
            max_iterations=max_iterations,
        )

        with console.status("[bold green]Thinking...", spinner="dots"):
            reply, tools_used = await agent.run(message)

        # Display tools used if any
        if tools_used:
            console.print(f"\n[dim]Tools used: {', '.join(tools_used)}[/dim]")

        # Display the response as markdown
        console.print()
        console.print(Panel(
            Markdown(reply),
            title="[bold]Response[/bold]",
            border_style="green",
        ))

    asyncio.run(_run())


@app.command()
def version() -> None:
    """Show version information."""
    from skills_executor import __version__
    console.print(f"[bold blue]python-skill-bot[/bold blue] version {__version__}")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()

