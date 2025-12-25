"""
Local tools for Claude API agent
"""

import os

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Import calendar functions
from icloud.calendar import (
    query_events,
    create_event,
    update_event,
    query_reminders,
    create_reminder,
    update_reminder,
)


# Configuration: Directory to search for markdown files
MARKDOWN_DIRECTORY = (
    "/Users/kckc/Library/Mobile Documents/iCloud~md~obsidian/Documents/Family/"
)

# Configuration: Path to todo list file
TODO_FILE_PATH = os.path.join(MARKDOWN_DIRECTORY, "Family Todo.md")


def get_current_datetime() -> Dict[str, Any]:
    """Get the current date and time with timezone information"""
    try:
        # Get current datetime with local timezone
        now = datetime.now().astimezone()

        return now.isoformat()
    except Exception as e:
        return {"error": str(e)}


def list_markdown_files() -> Dict[str, Any]:
    """List all markdown files in the configured directory (non-recursive)"""
    try:
        directory = Path(MARKDOWN_DIRECTORY)

        if not directory.exists():
            return {"error": f"Directory does not exist: {MARKDOWN_DIRECTORY}"}

        if not directory.is_dir():
            return {"error": f"Path is not a directory: {MARKDOWN_DIRECTORY}"}

        # Find all .md and .markdown files in the directory (non-recursive)
        markdown_files = []
        for pattern in [
            "*.md",
        ]:
            markdown_files.extend(directory.glob(pattern))

        # Sort by name and convert to strings
        files = sorted([f.name for f in markdown_files if not f.name.startswith(".")])

        return "\n".join(files)
    except Exception as e:
        return {"error": str(e)}


def read_markdown_file(filename: str) -> Dict[str, Any]:
    """
    Read the content of a markdown file from the configured directory.
    Only files listed by list_markdown_files() can be read.
    """
    try:
        if not filename:
            return {"error": "Missing required argument: filename"}

        # Validate directory exists
        directory = Path(MARKDOWN_DIRECTORY)
        if not directory.exists():
            return {"error": f"Directory does not exist: {MARKDOWN_DIRECTORY}"}

        if not directory.is_dir():
            return {"error": f"Path is not a directory: {MARKDOWN_DIRECTORY}"}

        # Construct the full path
        file_path = directory / filename

        # Security: Resolve both paths and ensure the file is within the allowed directory
        resolved_file = file_path.resolve()

        # Check if file exists
        if not resolved_file.exists():
            return {
                "error": f"File not found: {filename}. Use list_markdown_files() to see available files."
            }

        # Check if it's a file (not a directory)
        if not resolved_file.is_file():
            return {"error": f"Not a file: {filename}"}

        # Check if it has a .md extension
        if resolved_file.suffix.lower() not in [".md", ".markdown"]:
            return {
                "error": f"Invalid file type: {filename}. Only .md files can be read."
            }

        # Read the file content
        content = resolved_file.read_text(encoding="utf-8")

        return content
    except Exception as e:
        return {"error": str(e)}


def write_markdown_file(filename: str, content: str) -> Dict[str, Any]:
    """
    Write content to a markdown file in the configured directory.
    Creates a new file or overwrites an existing file.
    """
    try:
        if not filename:
            return {"error": "Missing required argument: filename"}

        if not content:
            return {"error": "Missing required argument: content"}

        # Validate directory exists
        directory = Path(MARKDOWN_DIRECTORY)
        if not directory.exists():
            return {"error": f"Directory does not exist: {MARKDOWN_DIRECTORY}"}

        if not directory.is_dir():
            return {"error": f"Path is not a directory: {MARKDOWN_DIRECTORY}"}

        # Validate filename doesn't contain path separators
        if "/" in filename or "\\" in filename:
            return {
                "error": f"Invalid filename: {filename}. Filename must not contain path separators."
            }

        # Ensure filename has .md extension
        if not filename.endswith(".md"):
            return {
                "error": f"Invalid filename: {filename}. Filename must end with .md extension."
            }

        # Construct the full path
        file_path = directory / filename

        # Security: Resolve both paths and ensure the file is within the allowed directory
        resolved_file = file_path.resolve()
        resolved_directory = directory.resolve()

        # Check if the resolved file path is within the allowed directory
        if not str(resolved_file).startswith(str(resolved_directory)):
            return {
                "error": f"Access denied: File must be in {MARKDOWN_DIRECTORY}. Path traversal detected."
            }

        # Write the content to the file
        resolved_file.write_text(content, encoding="utf-8")

        return f"Successfully wrote {len(content)} characters to {filename}"
    except Exception as e:
        return {"error": str(e)}


def list_todos() -> Dict[str, Any]:
    """
    List all todo items from the markdown file.
    Returns only unticked items in a table format with id and description
    """
    try:
        file_path = Path(TODO_FILE_PATH)

        if not file_path.exists():
            return {"error": f"Todo file not found: {TODO_FILE_PATH}"}

        # Read the file content
        content = file_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Parse todos
        todos = []
        for line in lines:
            line = line.strip()
            if line.startswith("- [ ]"):
                # Unticked item
                description = line[6:].strip()  # Remove "- [ ] " prefix
                todos.append({"completed": False, "description": description})
            elif line.startswith("- [x]") or line.startswith("- [X]"):
                # Ticked item (skip these)
                continue

        # Format as table
        if not todos:
            return "No incomplete todos found."

        # Create table
        result = "| Todo ID | Description |\n"
        result += "|---------|-------------|\n"
        for idx, todo in enumerate(todos, start=1):
            result += f"| {idx} | {todo['description']} |\n"

        return result
    except Exception as e:
        return {"error": str(e)}


def add_todo(description: str) -> Dict[str, Any]:
    """
    Add a new todo item to the markdown file.

    Args:
        description: The todo description text
    """
    try:
        if not description:
            return {"error": "Description cannot be empty"}

        file_path = Path(TODO_FILE_PATH)

        # Create file if it doesn't exist
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("", encoding="utf-8")

        # Read existing content
        content = file_path.read_text(encoding="utf-8")

        # Add new todo
        new_todo = f"- [ ] {description}\n"

        # Append to file
        if content and not content.endswith("\n"):
            content += "\n"
        content += new_todo

        # Write back to file
        file_path.write_text(content, encoding="utf-8")

        return f"Successfully added todo: {description}"
    except Exception as e:
        return {"error": str(e)}


def delete_todo(todo_id: int) -> Dict[str, Any]:
    """
    Delete a todo item by its ID.

    Args:
        todo_id: The ID of the todo to delete (from list_todos)
    """
    try:
        file_path = Path(TODO_FILE_PATH)

        if not file_path.exists():
            return {"error": f"Todo file not found: {TODO_FILE_PATH}"}

        # Read the file content
        content = file_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Parse unticked todos
        unticked_lines = []
        all_lines = []
        unticked_indices = []

        for idx, line in enumerate(lines):
            all_lines.append(line)
            if line.strip().startswith("- [ ]"):
                unticked_lines.append(line)
                unticked_indices.append(idx)

        # Validate todo_id
        if todo_id < 1 or todo_id > len(unticked_lines):
            return {
                "error": f"Invalid todo ID: {todo_id}. Valid range: 1-{len(unticked_lines)}"
            }

        # Get the line index to delete
        line_to_delete = unticked_indices[todo_id - 1]

        # Remove the line
        all_lines.pop(line_to_delete)

        # Write back to file
        new_content = "\n".join(all_lines)
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        file_path.write_text(new_content, encoding="utf-8")

        return f"Successfully deleted todo ID: {todo_id}"
    except Exception as e:
        return {"error": str(e)}


def update_todo(todo_id: int, description: str) -> Dict[str, Any]:
    """
    Update the description of an existing todo item.

    Args:
        todo_id: The ID of the todo to update (from list_todos)
        description: The new description text
    """
    try:
        if not description:
            return {"error": "Description cannot be empty"}

        file_path = Path(TODO_FILE_PATH)

        if not file_path.exists():
            return {"error": f"Todo file not found: {TODO_FILE_PATH}"}

        # Read the file content
        content = file_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")

        # Parse unticked todos
        unticked_lines = []
        all_lines = []
        unticked_indices = []

        for idx, line in enumerate(lines):
            all_lines.append(line)
            if line.strip().startswith("- [ ]"):
                unticked_lines.append(line)
                unticked_indices.append(idx)

        # Validate todo_id
        if todo_id < 1 or todo_id > len(unticked_lines):
            return {
                "error": f"Invalid todo ID: {todo_id}. Valid range: 1-{len(unticked_lines)}"
            }

        # Get the line index to update
        line_to_update = unticked_indices[todo_id - 1]

        # Update the line
        all_lines[line_to_update] = f"- [ ] {description}"

        # Write back to file
        new_content = "\n".join(all_lines)
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        file_path.write_text(new_content, encoding="utf-8")

        return f"Successfully updated todo ID {todo_id} to: {description}"
    except Exception as e:
        return {"error": str(e)}


# Tool definitions in Claude API format
LOCAL_TOOLS = [
    {
        "name": "get_current_datetime",
        "description": "Returns the current date and time. (timezone is Asia/Singapore timezone)",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "markdown__list_markdown_files",
        "description": f"Lists all markdown files (extension .md) in the configured directory: {MARKDOWN_DIRECTORY}. Use this tool to get the list of available file names before reading them.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "markdown__read_markdown_file",
        "description": f"Reads the content of a markdown file from the directory: {MARKDOWN_DIRECTORY}. IMPORTANT: Only files returned by list_markdown_files() can be read. Provide the exact filename (not a path) as returned by list_markdown_files().",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name of the markdown file to read (e.g., 'example.md'). Must be a file name returned by list_markdown_files().",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "markdown__write_markdown_file",
        "description": f"Writes content to a markdown file in the directory: {MARKDOWN_DIRECTORY}. Creates a new file or overwrites an existing file. The filename must end with .md extension and must not contain path separators.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The name of the markdown file to write (e.g., 'example.md'). Must end with .md extension and must not contain path separators (/, \\).",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "todo__list_todos",
        "description": f"Lists all outstanding todo items. Returns todo_ids and their description",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "todo__add_todo",
        "description": "Adds a new todo item to the todo markdown file. The todo will initiall be outstanding.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "The description text for the new todo item.",
                }
            },
            "required": ["description"],
        },
    },
    {
        "name": "todo__delete_todo",
        "description": "Deletes a todo item by its ID. Use list_todos() to see the current todos and their IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {
                    "type": "integer",
                    "description": "The ID of the todo item to delete (from list_todos()).",
                }
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "todo__update_todo",
        "description": "Updates the an existing todo item. Use list_todos() to see the current todos and their IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {
                    "type": "integer",
                    "description": "The ID of the todo item to update (from list_todos()).",
                },
                "description": {
                    "type": "string",
                    "description": "The new description text for the todo item.",
                },
            },
            "required": ["todo_id", "description"],
        },
    },
    {
        "name": "calendar__query_events",
        "description": "Query calendar events within a date range. Returns a table with event IDs, dates, names, and notes. Calendar names can be 'EVENTS', 'ACTIVITIES', or None (default, searches both).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format (e.g., '2025-01-01' or '2025-01-01T00:00:00')",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format (e.g., '2025-12-31' or '2025-12-31T23:59:59')",
                },
                "calendar_name": {
                    "type": "string",
                    "description": "Optional calendar name: 'EVENTS', 'ACTIVITIES', or omit for both calendars",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "calendar__create_event",
        "description": "Create a new calendar event. Things that we need to actively participates are in calendar_name = ACTIVITIES. Otherwise if we merely observing, e.g. school holiday, use EVENTS. Returns the event UUID on success.",
        "input_schema": {
            "type": "object",
            "properties": {
                "calendar_name": {
                    "type": "string",
                    "description": "Calendar name: must be either 'EVENTS' or 'ACTIVITIES'",
                },
                "title": {
                    "type": "string",
                    "description": "Event title",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Start date/time in ISO format (e.g., '2025-01-01T14:00:00')",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Optional end date/time in ISO format. Defaults to 1 hour after start if not provided. For multi day events MAKE SURE THIS HAS THE VALUE FOR END DATE",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes for the event",
                },
                "is_all_day": {
                    "type": "boolean",
                    "description": "Whether this is an all-day event. Defaults to false.",
                },
            },
            "required": ["calendar_name", "title", "start_datetime"],
        },
    },
    {
        "name": "calendar__update_event",
        "description": "Update an existing calendar event by its UUID. Only provide the fields you want to update.",
        "input_schema": {
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "The event UUID (from query_events)",
                },
                "title": {
                    "type": "string",
                    "description": "Optional new title for the event",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Optional new start date/time in ISO format",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Optional new end date/time in ISO format",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional new notes",
                },
                "is_all_day": {
                    "type": "boolean",
                    "description": "Optional: set to true to make this an all-day event",
                },
                "calendar_name": {
                    "type": "string",
                    "description": "Optional: move to different calendar ('EVENTS' or 'ACTIVITIES')",
                },
            },
            "required": ["uuid"],
        },
    },
    {
        "name": "calendar__query_reminders",
        "description": "Query all incomplete reminders from the TODO calendar. Returns a table with reminder IDs, titles, and due dates sorted by due date.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "calendar__create_reminder",
        "description": "Create a new reminder in the TODO calendar. Reminders are things that needs to be done before due day. Returns the reminder UUID on success.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Reminder title",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional due date in ISO format (e.g., '2025-01-01' or '2025-01-01T14:00:00')",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes for the reminder",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "calendar__update_reminder",
        "description": "Update an existing reminder by its UUID. Only provide the fields you want to update.",
        "input_schema": {
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "The reminder UUID (from query_reminders)",
                },
                "title": {
                    "type": "string",
                    "description": "Optional new title",
                },
                "due_date": {
                    "type": "string",
                    "description": "Optional new due date in ISO format",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional new notes",
                },
            },
            "required": ["uuid"],
        },
    },
]


# Map tool names to their implementation functions
TOOL_HANDLERS = {
    "get_current_datetime": get_current_datetime,
    "markdown__list_markdown_files": list_markdown_files,
    "markdown__read_markdown_file": read_markdown_file,
    "markdown__write_markdown_file": write_markdown_file,
    "todo__list_todos": list_todos,
    "todo__add_todo": add_todo,
    "todo__delete_todo": delete_todo,
    "todo__update_todo": update_todo,
    "calendar__query_events": query_events,
    "calendar__create_event": create_event,
    "calendar__update_event": update_event,
    "calendar__query_reminders": query_reminders,
    "calendar__create_reminder": create_reminder,
    "calendar__update_reminder": update_reminder,
}


def execute_local_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a local tool by name

    Args:
        tool_name: Name of the tool to execute
        arguments: Arguments to pass to the tool (currently unused)

    Returns:
        Result from the tool execution or error information
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        return handler(**arguments)
    except Exception as e:
        return {"error": str(e), "exception_type": type(e).__name__}
