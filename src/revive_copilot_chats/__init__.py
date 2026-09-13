"""
revive_copilot_chats — recover orphaned GitHub Copilot Chat sessions from
VS Code workspaceStorage folders whose original project path no longer
resolves (moved, renamed, or deleted).
"""

__version__ = "0.1.0"

from .merge import (
    read_chat_index,
    merge_indexes,
    write_chat_index,
    merge_folder,
    revive,
)
from .discovery import discover_all_sources, find_new_workspace_hash
from .workspace import create_and_discover_workspace
from .backup import backup_target_state_db
from .dates import parse_date_to_ms, filter_entries_by_date

__all__ = [
    "read_chat_index",
    "merge_indexes",
    "write_chat_index",
    "merge_folder",
    "revive",
    "discover_all_sources",
    "find_new_workspace_hash",
    "create_and_discover_workspace",
    "backup_target_state_db",
    "parse_date_to_ms",
    "filter_entries_by_date",
]
