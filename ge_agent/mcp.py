from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from .config import DEVELOPER_KNOWLEDGE_API_KEY

documentation_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url="https://developerknowledge.googleapis.com/mcp",
        headers={"X-Goog-Api-Key": DEVELOPER_KNOWLEDGE_API_KEY},
    ),
)
