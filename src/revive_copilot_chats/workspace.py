"""Opening VS Code to mint a brand-new workspaceStorage hash, with a
safety confirmation before we touch anything."""

import shutil as _shutil
import subprocess
import time
from pathlib import Path

from .discovery import find_new_workspace_hash


def create_and_discover_workspace(target_folder_path: str, storage_base: Path = None) -> str:
    """
    Opens target_folder_path in VS Code (creating it if needed), then asks
    the user to confirm they've fully quit VS Code before proceeding —
    writing to state.vscdb while VS Code still has it open will fail or
    risk corruption, so we don't guess; we ask.
    """
    if _shutil.which("code") is None:
        raise RuntimeError(
            "Stopped: the 'code' command was not found on your PATH, so VS Code "
            "cannot be opened automatically.\n\n"
            "To fix this:\n"
            "  1. Open VS Code manually.\n"
            "  2. Press Cmd+Shift+P to open the Command Palette.\n"
            "  3. Run: \"Shell Command: Install 'code' command in PATH\"\n"
            "  4. Re-run this script.\n\n"
            "Alternatively, skip --name and pass an existing workspaceStorage/<hash> "
            "folder as the target directly, e.g.:\n"
            "  revive-chats <target_workspace_dir> <source_dir> [source2_dir ...]"
        )

    if storage_base is None:
        storage_base = Path.home() / "Library/Application Support/Code/User/workspaceStorage"

    Path(target_folder_path).mkdir(parents=True, exist_ok=True)

    before = {d.name for d in storage_base.iterdir() if d.is_dir()}

    subprocess.Popen(["code", "--new-window", target_folder_path])
    time.sleep(3)  # give VS Code time to register the workspace and write workspace.json

    print(f"\nA new VS Code window has been opened for: {target_folder_path}")
    print("IMPORTANT: You must fully QUIT VS Code now (Cmd+Q), not just close the window.")
    print("If VS Code is still running, its state.vscdb file will be locked and the")
    print("merge step below will fail or could corrupt the workspace data.\n")

    while True:
        answer = input("Have you fully quit VS Code? (yes/no): ").strip().lower()
        if answer in ("yes", "y"):
            break
        if answer in ("no", "n"):
            raise RuntimeError(
                "Stopped: VS Code must be fully quit before the merge can proceed safely. "
                "Quit VS Code (Cmd+Q) and re-run this command when ready."
            )
        print("Please answer 'yes' or 'no'.")

    after = {d.name for d in storage_base.iterdir() if d.is_dir()}
    brand_new = after - before

    if len(brand_new) == 1:
        return brand_new.pop()  # unambiguous: exactly one new folder appeared

    # fall back to recency+verification scan (covers 0-new or multiple-new cases)
    found = find_new_workspace_hash(target_folder_path, storage_base)
    if found:
        return found

    raise RuntimeError(
        f"Could not determine workspace hash for {target_folder_path}. "
        "Try opening it manually in VS Code once, then re-run pointing "
        "directly at the workspaceStorage/<hash> folder."
    )
