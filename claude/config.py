"""
Configuration file for Claude MCP Agent
Edit these values with your actual API key and MCP server details
"""

import os

CLAUDE_API_KEY = os.environ["CLAUDE_API_KEY"]
MCP_SERVER_URLS = (
    []
)  # ["http://192.168.50.142:38000/mcp", "http://192.168.50.142:38001/mcp"]
CLAUDE_MODEL = "claude-opus-4-5-20251101"

# Optional: Advanced configuration
CLAUDE_MAX_TOKENS = 4096
REQUEST_TIMEOUT = 30
