# import asyncio
# import json
# import sqlite3
# import uuid
# from datetime import datetime
# from typing import Any, Dict, List, Optional

# from anthropic import Anthropic
# from anthropic.types import (
#     Message,
#     TextBlock,
#     ToolUseBlock,
# )
# from anthropic.types.beta import BetaTextBlock

# from fastmcp import Client


# class ClaudeMCPAgent:
#     """Agent that connects Claude to an HTTP MCP server"""

#     def __init__(self, config: Config):
#         self.config = config
#         self.client = Anthropic(api_key=config.claude_api_key)
#         self.mcp_clients: Dict[str, Client] = {}
#         self.tools: List[Dict[str, Any]] = LOCAL_TOOLS.copy()

#     async def initialize(self) -> None:
#         """Initialize the agent by fetching tools from MCP server"""
#         if self.config.mcp_server_urls:
#             for url in self.config.mcp_server_urls:
#                 print(f"Connecting to MCP server at {self.config.mcp_server_urls}...")

#                 # Create FastMCP client
#                 mcp_client = Client(
#                     url,
#                     timeout=self.config.request_timeout,
#                 )

#                 # Fetch available tools
#                 tools = await self._fetch_tools(mcp_client)

#                 print(f"✓ Loaded {len(tools)} tools from MCP server")

#                 if tools:
#                     self.tools.extend(tools)
#                     print("\nAvailable tools:")
#                     for tool in tools:
#                         print(
#                             f"  - {tool['name']}: {tool.get('description', 'No description')}"
#                         )
#                         self.mcp_clients[tool["name"]] = mcp_client

#     async def _fetch_tools(self, mcp_client: Client) -> List[Dict[str, Any]]:
#         """Fetch available tools from MCP server"""
#         try:
#             if not mcp_client:
#                 raise Exception("MCP client not initialized")

#             # Use FastMCP client to list tools
#             async with mcp_client:
#                 mcp_tools = await mcp_client.list_tools()

#                 # Convert MCP tool format to Claude tool format
#                 return self._convert_mcp_tools_to_claude_format(mcp_tools)
#         except Exception as e:
#             print(f"Error fetching tools from MCP server: {e}")
#             return []

#     def _convert_mcp_tools_to_claude_format(
#         self, mcp_tools: List[Any]
#     ) -> List[Dict[str, Any]]:
#         """Convert MCP tool schema to Claude's expected format"""
#         claude_tools = []
#         for tool in mcp_tools:
#             # FastMCP returns mcp.types.Tool objects
#             claude_tool = {
#                 "name": tool.name,
#                 "description": tool.description or "",
#                 "input_schema": tool.inputSchema
#                 or {"type": "object", "properties": {}},
#             }
#             claude_tools.append(claude_tool)
#         return claude_tools

#     async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
#         """Execute a tool via the MCP server or local tool call"""
#         # Check if it's a local tool
#         if tool_name in TOOL_HANDLERS:
#             return execute_local_tool(tool_name, tool_input)

#         try:
#             mcp_client = self.mcp_clients.get(tool_name)
#             if not mcp_client:
#                 raise Exception("MCP client not initialized")

#             # Use FastMCP client to call tool
#             async with mcp_client:
#                 result = await mcp_client.call_tool(
#                     name=tool_name,
#                     arguments=tool_input,
#                     raise_on_error=False,  # Handle errors gracefully
#                 )

#                 # Convert CallToolResult to a dictionary for Claude
#                 # If there's structured content, return it; otherwise return text content
#                 if result.structured_content:
#                     return result.structured_content

#                 # Extract text from content blocks
#                 response_text = []
#                 for content in result.content:
#                     if hasattr(content, "text"):
#                         response_text.append(content.text)

#                 if response_text:
#                     return {"result": "\n".join(response_text)}

#                 return {"result": "Tool executed successfully"}
#         except Exception as e:
#             return {"error": str(e)}

#     async def chat(
#         self,
#         conversation_history: List[Dict[str, Any]],
#         system_prompt: Optional[str] = None,
#         betas: Optional[List[str]] = None,
#         **kwargs,
#     ) -> str:
#         """
#         Send a message to Claude and handle tool use in a loop

#         Args:
#             conversation_history: list of messages
#             system_prompt: Optional system prompt to guide Claude's behavior

#         Returns:
#             Claude's final response as a string
#         """
#         # Process the conversation with potential tool use
#         while True:
#             # Prepare the API call

#             # print("---------------")
#             # from pprint import pp

#             # for m in conversation_history:
#             #     pp(m)
#             # print("----------------")
#             api_params = {**kwargs}

#             api_params.update(
#                 {
#                     "model": self.config.claude_model,
#                     "max_tokens": self.config.claude_max_tokens,
#                     "messages": conversation_history,
#                 }
#             )

#             # Add tools if available
#             if self.tools:
#                 api_params["tools"] = self.tools

#             # Add system prompt if provided
#             if system_prompt:
#                 api_params["system"] = system_prompt

#             # Call Claude API
#             if betas:
#                 response: Message = self.client.beta.messages.create(
#                     **api_params, betas=betas
#                 )
#             else:
#                 response: Message = self.client.messages.create(**api_params)

#             # Check if Claude wants to use tools
#             tool_use_blocks = [
#                 block for block in response.content if isinstance(block, ToolUseBlock)
#             ]

#             if not tool_use_blocks:
#                 # No tool use, extract and return the text response
#                 text_blocks = [
#                     block
#                     for block in response.content
#                     if isinstance(block, (TextBlock, BetaTextBlock))
#                 ]
#                 response_text = "\n".join(block.text for block in text_blocks)

#                 # Add assistant's response to history
#                 conversation_history.append(
#                     {"role": "assistant", "content": response_text}
#                 )

#                 return response_text

#             # Execute all requested tools
#             for tool_use in tool_use_blocks:
#                 print(f"\n🔧 Executing tool: {tool_use.name}")
#                 print(f"   Input: {json.dumps(tool_use.input, indent=2)}")

#                 result = await self._execute_tool(tool_use.name, tool_use.input)

#                 print(f"   Result: {json.dumps(result, indent=2)}")
#                 conversation_history.append(
#                     {"role": "assistant", "content": [tool_use.model_dump()]}
#                 )
#                 conversation_history.append(
#                     {
#                         "role": "user",
#                         "content": [
#                             {
#                                 "type": "tool_result",
#                                 "tool_use_id": tool_use.id,
#                                 "content": json.dumps(result),
#                             }
#                         ],
#                     }
#                 )
