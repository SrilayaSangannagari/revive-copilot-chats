"""Shared constants."""

from pathlib import Path

CHAT_INDEX_KEY = "chat.ChatSessionStore.index"
FOLDERS_TO_MERGE = ["chatSessions", "chatEditingSessions", "GitHub.copilot-chat"]

DEFAULT_BASE_DIR = Path.home() / "Desktop"
DEFAULT_STORAGE_BASE = (
    Path.home() / "Library/Application Support/Code/User/workspaceStorage"
)
