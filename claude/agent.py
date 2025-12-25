import asyncio
import json
import os
import sqlite3
import uuid

from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from anthropic.types import (
    Message,
    TextBlock,
    ToolUseBlock,
)
from anthropic.types.beta import BetaTextBlock

from .config import (
    CLAUDE_API_KEY,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    REQUEST_TIMEOUT,
)

from .tools import LOCAL_TOOLS, execute_local_tool

DATA_PATH = os.environ["DB_PATH"]
DB_PATH = os.path.join(DATA_PATH, "claude_conversation.db")


class Config:
    """Configuration for Claude Agent"""

    def __init__(
        self,
        claude_api_key: str = CLAUDE_API_KEY,
        claude_model: str = CLAUDE_MODEL,
        claude_max_tokens: int = CLAUDE_MAX_TOKENS,
        request_timeout: int = REQUEST_TIMEOUT,
    ):
        self.claude_api_key = claude_api_key
        self.claude_model = claude_model
        self.claude_max_tokens = claude_max_tokens
        self.request_timeout = request_timeout


class DummyAgent:
    def __init__(self, *args, **kwargs):
        pass

    async def initialize(self) -> None:
        pass

    async def chat(
        self,
        conversation_history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> str:
        conversation_history.append({"role": "assistant", "content": "some content"})
        print("----------")
        for c in conversation_history:
            print(c)

        return "some content"


STRUCTURED_OUTPUT_HEADER = "structured-outputs-2025-11-13"


class ClaudeSimpleBetaAgent:
    def __init__(self, config: Config):
        self.config = config
        self.client = Anthropic(api_key=config.claude_api_key)

    async def initialize(self) -> None:
        pass

    async def chat(
        self,
        conversation_history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Send a message to Claude and handle tool use in a loop

        Args:
            conversation_history: list of messages
            system_prompt: Optional system prompt to guide Claude's behavior

        Returns:
            Claude's final response as a string
        """
        # Prepare the API call
        api_params = {**kwargs}

        api_params.update(
            {
                "model": self.config.claude_model,
                "max_tokens": self.config.claude_max_tokens,
                "messages": conversation_history,
            }
        )

        # Add system prompt if provided
        if system_prompt:
            api_params["system"] = system_prompt

        betas: list = kwargs.get("betas", [])
        if kwargs.get("output_format") and STRUCTURED_OUTPUT_HEADER not in betas:
            betas.append(STRUCTURED_OUTPUT_HEADER)

        # Call Claude API
        if betas:
            response: Message = self.client.beta.messages.create(
                **api_params, betas=betas
            )
        else:
            response: Message = self.client.messages.create(**api_params)

        response_text = response.content[0].text

        # Add assistant's response to history
        conversation_history.append({"role": "assistant", "content": response_text})

        return response_text


class ClaudeAgent:
    def __init__(self, config: Config):
        self.config = config
        self.client = Anthropic(api_key=config.claude_api_key)
        self.tools: List[Dict[str, Any]] = LOCAL_TOOLS.copy()

    async def initialize(self) -> None:
        pass

    async def chat(
        self,
        conversation_history: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        betas: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """
        Send a message to Claude and handle tool use in a loop

        Args:
            conversation_history: list of messages
            system_prompt: Optional system prompt to guide Claude's behavior

        Returns:
            Claude's final response as a string
        """
        # Process the conversation with potential tool use
        while True:
            # Prepare the API call

            # print("---------------")
            # from pprint import pp

            # for m in conversation_history:
            #     pp(m)
            # print("----------------")
            api_params = {**kwargs}

            api_params.update(
                {
                    "model": self.config.claude_model,
                    "max_tokens": self.config.claude_max_tokens,
                    "messages": conversation_history,
                }
            )

            # Add tools if available
            if self.tools:
                api_params["tools"] = self.tools

            # Add system prompt if provided
            if system_prompt:
                api_params["system"] = system_prompt

            # Call Claude API
            if betas:
                response: Message = self.client.beta.messages.create(
                    **api_params, betas=betas
                )
            else:
                response: Message = self.client.messages.create(**api_params)

            # Check if Claude wants to use tools
            tool_use_blocks = [
                block for block in response.content if isinstance(block, ToolUseBlock)
            ]

            if not tool_use_blocks:
                # No tool use, extract and return the text response
                text_blocks = [
                    block
                    for block in response.content
                    if isinstance(block, (TextBlock, BetaTextBlock))
                ]
                response_text = "\n".join(block.text for block in text_blocks)

                # Add assistant's response to history
                conversation_history.append(
                    {"role": "assistant", "content": response_text}
                )

                return response_text

            # Execute all requested tools
            for tool_use in tool_use_blocks:
                print(f"\n🔧 Executing tool: {tool_use.name}")
                print(f"   Input: {json.dumps(tool_use.input, indent=2)}")

                result = execute_local_tool(tool_use.name, tool_use.input)

                print(f"   Result: {json.dumps(result, indent=2)}")
                conversation_history.append(
                    {"role": "assistant", "content": [tool_use.model_dump()]}
                )
                conversation_history.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": json.dumps(result),
                            }
                        ],
                    }
                )


from pathlib import Path
from base64 import b64encode

EXT_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "pdf": "application/pdf",
}

SUPPORTED_MEDIA_TYPE = set(EXT_MAP.values())


def claude_image_block(image_path: Path):
    assert image_path.is_file(), f"Target not a file: {image_path}"

    _, _, ext = image_path.parts[-1].rpartition(".")
    with open(image_path, "rb") as f:
        bytes = f.read()

    media_type = EXT_MAP.get(ext)
    assert media_type, f"Unrecognised ext and media_type for: {image_path}"

    return claude_image_block_from_bytes(ext, bytes)


def claude_image_block_from_bytes(ext: str, b: bytes):
    media_type = EXT_MAP.get(ext)
    assert media_type, f"Unrecognised ext and media_type for: {ext}"

    data = b64encode(b).decode()

    return {
        "role": "user",
        "content": [
            {
                "source": {
                    "data": data,
                    "media_type": media_type,
                    "type": "base64",
                },
                "type": "image",
            }
        ],
    }


class InMemoryConversation:
    """Stateless agent that stores conversations in memory"""

    def __init__(self, agent: Any):
        self.agent = agent
        # Store conversations: {conversation_id: [messages]}
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        # Store metadata: {conversation_id: {created_at: str}}
        self.conversation_metadata: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Initialize the underlying agent"""
        return await self.agent.initialize()

    def _conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists in memory"""
        return conversation_id in self.conversations

    def _create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation entry in memory"""
        self.conversations[conversation_id] = []
        self.conversation_metadata[conversation_id] = {
            "created_at": datetime.now().isoformat()
        }

    def _load_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Load conversation history from memory"""
        return self.conversations.get(conversation_id, []).copy()

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations in memory"""
        conversations = []
        for conv_id in sorted(
            self.conversations.keys(),
            key=lambda k: self.conversation_metadata[k]["created_at"],
            reverse=True,
        ):
            conversations.append(
                {
                    "id": conv_id,
                    "created_at": self.conversation_metadata[conv_id]["created_at"],
                    "message_count": len(self.conversations[conv_id]),
                }
            )
        return conversations

    async def chat(
        self,
        user_message: str | dict[str, Any] | list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Send a message to Claude and handle tool use in a loop

        Args:
            user_message: The user's message
            conversation_id: Optional conversation ID. If not provided, a new one is generated.
            system_prompt: Optional system prompt to guide Claude's behavior

        Returns:
            Tuple of (response text, conversation_id)
        """
        # Generate new conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # Create conversation if it doesn't exist
        if not self._conversation_exists(conversation_id):
            self._create_conversation(conversation_id)

        # Load existing conversation history from memory
        conversation_history = self._load_conversation(conversation_id)

        # Add user message to history
        if not isinstance(user_message, list):
            user_message = [user_message]

        for u in user_message:
            if isinstance(u, dict):
                if u.get("media_type") not in SUPPORTED_MEDIA_TYPE:
                    continue

                u = [
                    {
                        "source": u,
                        "type": (
                            "document"
                            if u["media_type"] == "application/pdf"
                            else "image"
                        ),
                    }
                ]

            msg = {"role": "user", "content": u}
            conversation_history.append(msg)

        # Get response from agent (this modifies conversation_history in place)
        response = await self.agent.chat(
            conversation_history, system_prompt=system_prompt
        )

        # Save the entire updated conversation history back to memory
        self.conversations[conversation_id] = conversation_history

        return conversation_id, response


class SQLiteConversation:
    """Stateless agent that persists conversations to SQLite database"""

    def __init__(self, agent: Any, db_path: str):
        self.agent = agent
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Create database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create conversations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )

            # Create messages table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
                """
            )

            # Create index for faster lookups
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON messages (conversation_id)
                """
            )

            conn.commit()

    def _conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists in the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
            )
            return cursor.fetchone() is not None

    def _create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation entry in the database"""
        created_at = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (id, created_at) VALUES (?, ?)",
                (conversation_id, created_at),
            )
            conn.commit()

    def _save_message(self, conversation_id: str, role: str, content: Any) -> None:
        """Save a single message to the database"""
        created_at = datetime.now().isoformat()
        content_json = json.dumps(content)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content_json, created_at),
            )
            conn.commit()

    def _load_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Load conversation history from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            )

            messages = []
            for row in cursor.fetchall():
                role, content_json = row
                content = json.loads(content_json)
                messages.append({"role": role, "content": content})

            return messages

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations in the database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.id, c.created_at, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id, c.created_at
                ORDER BY c.created_at DESC
                """
            )

            conversations = []
            for row in cursor.fetchall():
                conv_id, created_at, message_count = row
                conversations.append(
                    {
                        "id": conv_id,
                        "created_at": created_at,
                        "message_count": message_count,
                    }
                )

            return conversations

    async def initialize(self) -> None:
        """Initialize the underlying agent"""
        await self.agent.initialize()

    async def chat(
        self,
        user_message: str | dict[str, Any] | list[dict[str, Any]],
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Send a message to Claude and handle tool use in a loop

        Args:
            user_message: The user's message
            conversation_id: Optional conversation ID. If not provided, a new one is generated.
            system_prompt: Optional system prompt to guide Claude's behavior

        Returns:
            Tuple of (response text, conversation_id)
        """
        # Generate new conversation ID if not provided
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # Create conversation if it doesn't exist
        if not self._conversation_exists(conversation_id):
            self._create_conversation(conversation_id)

        # Load existing conversation history from database
        conversation_history = self._load_conversation(conversation_id)

        # Add user message to history
        if not isinstance(user_message, list):
            user_message = [user_message]

        for u in user_message:
            if isinstance(u, dict):
                if u.get("media_type") not in SUPPORTED_MEDIA_TYPE:
                    continue

                u = [
                    {
                        "source": u,
                        "type": (
                            "document"
                            if u["media_type"] == "application/pdf"
                            else "image"
                        ),
                    }
                ]

            msg = {"role": "user", "content": u}
            self._save_message(conversation_id, "user", u)
            conversation_history.append(msg)

        # Track the number of messages before agent call
        initial_message_count = len(conversation_history)

        from pprint import pp

        pp(conversation_history)

        # Get response from agent (this modifies conversation_history in place)
        response = await self.agent.chat(
            conversation_history, system_prompt=system_prompt
        )

        # Save all new messages that were added by the agent
        # (assistant responses and tool results)
        for message in conversation_history[initial_message_count:]:
            self._save_message(conversation_id, message["role"], message["content"])

        return conversation_id, response


async def _init():
    agent = SQLiteConversation(ClaudeAgent(Config()), DB_PATH)
    await agent.initialize()
    return agent


def sync_chat():
    agent = asyncio.run(_init())

    def _fn(text, previous_response_id):
        return asyncio.run(agent.chat(text, conversation_id=previous_response_id))

    return _fn


async def interactive_mode():
    """Run the agent in interactive chat mode"""
    print("=" * 60)
    print("Claude Agent - Interactive Mode")
    print("=" * 60)

    # Initialize configuration
    config = Config()

    # Validate configuration
    if config.claude_api_key == "YOUR_CLAUDE_API_KEY_HERE":
        print("\n❌ Error: Please set your Claude API key in config.py")
        return

    # Initialize agent
    agent = InMemoryConversation(DummyAgent(config))
    await agent.initialize()

    print("\n" + "=" * 60)
    print("Ready to chat! Type 'quit' or 'exit' to end the session.")
    print("Type 'reset' to clear conversation history.")
    print("=" * 60 + "\n")

    # Optional: Set a system prompt
    system_prompt = (
        "You are a helpful assistant with access to tools to help you answer user queries."
        "When you need to use a tool, explain what you're doing and why. "
        "After receiving tool results, provide a clear summary to the user."
    )

    conversation_id = None

    cached_user_input = ""
    partial_input = False

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            partial_input = False
            if user_input.endswith("\\"):
                user_input = user_input.removesuffix("\\")
                partial_input = True

            if cached_user_input:
                cached_user_input += "\n"
                cached_user_input += user_input
            else:
                cached_user_input = user_input

            if partial_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("\nGoodbye!")
                break

            if user_input.lower() == "reset":
                agent.reset_conversation()
                continue

            # Get response from Claude
            print("\nClaude: ", end="", flush=True)
            conversation_id, response = await agent.chat(
                cached_user_input,
                system_prompt=system_prompt,
                conversation_id=conversation_id,
            )
            cached_user_input = ""
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


async def main():
    """Main entry point"""
    await interactive_mode()
    # Initialize agent
    # config = Config()

    # agent = InMemoryConversation(ClaudeAgent(config))
    # await agent.initialize()

    # m1 = claude_image_block(
    #     Path(
    #         "/Users/kckc/Downloads/500px-Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg"
    #     )
    # )

    # _, r = await agent.chat([m1, "what animal is in the pic"])
    # print(r)


if __name__ == "__main__":
    asyncio.run(main())
