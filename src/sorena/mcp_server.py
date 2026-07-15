from mcp.server.fastmcp import FastMCP

from sorena.tools import file_search_tool, shell_tool, time_tool, web_search_tool

mcp = FastMCP("sorena")


@mcp.tool()
def get_current_time() -> str:
    """Get the current UTC time as an ISO 8601 string."""
    return time_tool.run()


@mcp.tool()
def search_files(pattern: str, root: str = ".") -> str:
    """Search for files by name (glob pattern) under a root directory."""
    return file_search_tool.run(pattern, root)


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web and return top results."""
    return web_search_tool.run(query)


@mcp.tool()
def run_shell_command(command: str) -> str:
    """Run an allow-listed shell command (whoami, hostname, git, where)."""
    return shell_tool.run(command)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
