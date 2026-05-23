from pathlib import Path

from langchain_core.tools import tool

from app.config import settings

WORKSPACE = Path(settings.demo_workspace)
WORKSPACE.mkdir(parents=True, exist_ok=True)

AVAILABLE_TOOLS = {
    "web_search": "Search the web for current information",
    "read_file": "Read a file from the demo workspace",
    "write_file": "Write a file to the demo workspace",
    "send_agent_message": "Send an async message to another agent",
    "notify_human": "Send a notification reply to the human user",
}


def _run_web_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No search results found."
        return "\n\n".join(
            f"**{r.get('title', 'Result')}**: {r.get('body', '')}" for r in results
        )
    except Exception as exc:
        return f"Search unavailable: {exc}. Use your knowledge to proceed."


async def prefetch_tool_context(tool_names: list[str], query: str) -> str:
    """Run selected tools without LLM tool-calling (avoids Groq/OpenCode tool name mismatches)."""
    sections: list[str] = []
    if "web_search" in tool_names:
        sections.append(f"Web search results for '{query[:200]}':\n{_run_web_search(query[:200])}")
    return "\n\n".join(sections)


def build_tools(selected: list[str], run_id: str | None = None):
    tools = []

    if "web_search" in selected:
        @tool
        def web_search(query: str) -> str:
            """Search the web for information on a topic."""
            return _run_web_search(query)

        tools.append(web_search)

    if "read_file" in selected:
        @tool
        def read_file(filename: str) -> str:
            """Read a file from the sandboxed demo workspace."""
            path = WORKSPACE / filename
            if not path.exists():
                return f"File not found: {filename}"
            return path.read_text(encoding="utf-8")

        tools.append(read_file)

    if "write_file" in selected:
        @tool
        def write_file(filename: str, content: str) -> str:
            """Write content to a file in the demo workspace."""
            path = WORKSPACE / filename
            path.write_text(content, encoding="utf-8")
            return f"Wrote {len(content)} chars to {filename}"

        tools.append(write_file)

    if "send_agent_message" in selected:
        @tool
        def send_agent_message(to_agent: str, message: str) -> str:
            """Send an async message to another agent in the workflow."""
            return f"Message queued for agent '{to_agent}': {message}"

        tools.append(send_agent_message)

    if "notify_human" in selected:
        @tool
        def notify_human(message: str) -> str:
            """Send a reply message to the human user."""
            return f"Human notification prepared: {message}"

        tools.append(notify_human)

    return tools


def list_available_tools() -> list[dict[str, str]]:
    return [{"name": k, "description": v} for k, v in AVAILABLE_TOOLS.items()]
