"""Command-line entry point: `revive-chats`."""

import argparse
import sqlite3
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
        "paths",
        nargs="*",
        help="Without --name: <target_workspace_dir> [source_dir ...] — first path "
             "is the target, the rest are sources. With --name: every path given "
             "is treated as a source (the target is created for you). Name no "
             "sources and every workspace under workspaceStorage is used.",
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
        help="Use every workspaceStorage/<hash> folder (except the target) as a "
             "source. This is already the default when you name no sources; pass "
             "it to add every workspace on top of sources you did name.",
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

    try:
        return _run(parser, args)
    except SystemExit as e:
        # parser.error() raises SystemExit directly. Converting it to a
        # normal return here is behaviorally identical for the actual CLI
        # (raise SystemExit(main()) in __main__ re-raises with the same
        # code) but makes main() usable as a plain function in tests.
        return e.code if isinstance(e.code, int) else 1
    except (RuntimeError, ValueError) as e:
        # Expected, already-clear error messages raised deliberately by the
        # tool — print them as-is, no traceback noise.
        print(f"\nERROR: {e}")
        return 1
    except sqlite3.DatabaseError as e:
        print(
            f"\nERROR: a state.vscdb file appears corrupted or unreadable: {e}\n"
            "If this is the target, restore from state.vscdb.backup if one exists."
        )
        return 1
    except PermissionError as e:
        print(
            f"\nERROR: permission denied accessing a file: {e}\n"
            "Check that you have read/write access to the relevant workspaceStorage folders."
        )
        return 1
    except EOFError:
        print(
            "\nERROR: this command needs to ask a yes/no question interactively "
            "(e.g. confirming VS Code is closed), but no terminal input is available.\n"
            "Run this directly in a terminal, not through a pipe or non-interactive script."
        )
        return 1


def _run(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    storage_base = Path(args.storage_base)

    # --- Validate dates upfront, with clear messages instead of raw tracebacks ---
    try:
        date_from_ms = parse_date_to_ms(args.date_from) if args.date_from else None
    except ValueError:
        parser.error(f"--from {args.date_from!r} is not a valid date. Use YYYY-MM-DD, e.g. 2026-02-01.")
    try:
        date_to_ms = parse_date_to_ms(args.date_to, end_of_day=True) if args.date_to else None
    except ValueError:
        parser.error(f"--to {args.date_to!r} is not a valid date. Use YYYY-MM-DD, e.g. 2026-02-28.")

    if date_from_ms is not None and date_to_ms is not None and date_from_ms > date_to_ms:
        parser.error(
            f"--from {args.date_from} is after --to {args.date_to} — the range is empty. "
            "Did you mean to swap them?"
        )

    # --- Resolve target and sources from the single 'paths' list ---
    # (Kept as one list, disambiguated by --name, so a source path can never
    # be silently mistaken for the target or vice versa.)
    if not args.name and not args.paths:
        parser.error(
            "Provide <target_workspace_dir> [source_dir ...], or use "
            "--name 'folder name' to create a fresh target."
        )

    explicit_sources = args.paths if args.name else args.paths[1:]

    # Naming no sources means "every workspace under workspaceStorage". That's
    # the common case: an orphaned workspace's hash is exactly what you don't
    # know, which is why its chats became unreachable. --scan-all is then only
    # needed to add every workspace *on top of* sources you did name.
    scan_all = args.scan_all or not explicit_sources

    # Checked before any folder is created or VS Code is launched, so --name
    # can't do all that work — and make you quit VS Code — only to fail after.
    if (args.name or scan_all) and not storage_base.exists():
        parser.error(
            f"--storage-base does not exist: {storage_base}\n"
            "Check the path, or omit --storage-base to use the default VS Code location."
        )

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
        target_dir = args.paths[0]
        target_hash = Path(target_dir).name

    # --- Resolve sources ---
    if scan_all:
        if not explicit_sources:
            print("No sources given — scanning every workspace under workspaceStorage.")
        discovered = discover_all_sources(storage_base, exclude_hashes={target_hash})
        sources = [str(d) for d in discovered] + explicit_sources
        print(f"Found {len(discovered)} candidate workspace(s) under {storage_base}")
    else:
        sources = explicit_sources

    # --- Never merge a workspace into itself ---
    target_resolved = Path(target_dir).resolve()
    deduped_sources = []
    for s in sources:
        if Path(s).resolve() == target_resolved:
            print(f"NOTE: skipping source {s} — it's the same as the target.")
            continue
        deduped_sources.append(s)
    sources = deduped_sources

    if not sources:
        print("\nNothing to do: no sources remain after filtering. Exiting.")
        return 0

    # --- Backup only the target's state.vscdb (the one file we write to) ---
    if not args.no_backup:
        try:
            backup_target_state_db(Path(target_dir) / "state.vscdb")
        except OSError as e:
            parser.error(
                f"Could not back up the target's state.vscdb: {e}\n"
                "Fix the underlying issue (disk space, permissions), or pass "
                "--no-backup to proceed without a safety copy (not recommended)."
            )
    else:
        print("Skipping backup (--no-backup given). Proceeding at your own risk.\n")

    revive(target_dir, sources, date_from_ms=date_from_ms, date_to_ms=date_to_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
