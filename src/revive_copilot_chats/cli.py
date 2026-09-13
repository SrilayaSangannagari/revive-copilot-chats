"""Command-line entry point: `revive-chats`."""

import argparse
from pathlib import Path

from .backup import backup_target_state_db
from .constants import DEFAULT_BASE_DIR, DEFAULT_STORAGE_BASE
from .dates import parse_date_to_ms
from .discovery import discover_all_sources
from .merge import revive
from .workspace import create_and_discover_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="revive-chats",
        description="Revive Copilot Chat sessions into a target VS Code workspace.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target workspaceStorage/<hash> folder (full path). Omit and use --name "
             "instead if you want a fresh workspace created for you.",
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="Source workspaceStorage/<hash> folder(s). Omit and use --scan-all "
             "instead to pull from every workspace under workspaceStorage.",
    )
    parser.add_argument(
        "--name",
        help="Create a fresh workspace with this folder name (e.g. 'revived chats') "
             "under --base-dir, auto-discover its hash, then merge into it.",
    )
    parser.add_argument(
        "--base-dir",
        default=str(DEFAULT_BASE_DIR),
        help=f"Where to create the new workspace folder when using --name. Default: {DEFAULT_BASE_DIR}",
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Automatically use every workspaceStorage/<hash> folder (except the "
             "target) as a source, instead of listing them individually.",
    )
    parser.add_argument(
        "--storage-base",
        default=str(DEFAULT_STORAGE_BASE),
        help=f"Path to workspaceStorage itself, used by --scan-all and --name. "
             f"Default: {DEFAULT_STORAGE_BASE}",
    )
    parser.add_argument(
        "--from", dest="date_from", default=None,
        help="Only merge sessions with lastMessageDate on/after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to", dest="date_to", default=None,
        help="Only merge sessions with lastMessageDate on/before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backing up the target's state.vscdb first. Not recommended.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    storage_base = Path(args.storage_base)

    date_from_ms = parse_date_to_ms(args.date_from) if args.date_from else None
    date_to_ms = parse_date_to_ms(args.date_to, end_of_day=True) if args.date_to else None

    # --- Resolve target ---
    if args.name:
        new_folder_path = str(Path(args.base_dir) / args.name)
        print(f"Creating workspace '{args.name}' at: {new_folder_path}")
        print("Opening in VS Code to register it...")
        hash_name = create_and_discover_workspace(new_folder_path, storage_base)
        target_dir = str(storage_base / hash_name)
        target_hash = hash_name
        print(f"Discovered new workspace hash: {hash_name}")
        print(f"Target workspaceStorage folder: {target_dir}\n")
    else:
        if not args.target:
            parser.error("Provide <target_workspace_dir>, or use --name 'folder name'.")
        target_dir = args.target
        target_hash = Path(target_dir).name

    # --- Resolve sources ---
    if args.scan_all:
        discovered = discover_all_sources(storage_base, exclude_hashes={target_hash})
        sources = [str(d) for d in discovered]
        print(f"--scan-all: found {len(sources)} candidate workspace(s) under {storage_base}")
    else:
        sources = args.sources
        if not sources:
            parser.error(
                "Provide at least one source workspaceStorage/<hash> folder, "
                "or use --scan-all to merge from every workspace automatically."
            )

    # --- Backup only the target's state.vscdb (the one file we write to) ---
    if not args.no_backup:
        backup_target_state_db(Path(target_dir) / "state.vscdb")
    else:
        print("Skipping backup (--no-backup given). Proceeding at your own risk.\n")

    revive(target_dir, sources, date_from_ms=date_from_ms, date_to_ms=date_to_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
