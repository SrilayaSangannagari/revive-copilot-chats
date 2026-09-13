# revive-copilot-chats

Recover GitHub Copilot Chat sessions from VS Code workspaces that have
become **orphaned** — their `workspaceStorage/<hash>` folder still exists
on disk, but the original project folder was moved, renamed, or deleted,
so VS Code no longer links back to it and the chats become invisible in
the Chat History panel.

## Why this happens

VS Code stores Copilot Chat sessions under
`workspaceStorage/<hash>/chatSessions/`, where `<hash>` is derived from
the workspace folder's path. If that folder is moved or deleted (or was
an untitled/multi-root workspace VS Code garbage-collected), the link is
severed — but the chat data itself is still sitting on disk, fully
readable, just unreachable through the UI.

## How it works

For each source workspace, this tool:

1. Merges the `chat.ChatSessionStore.index` key from the source's
   `state.vscdb` into the target's — the catalog entry that makes a
   session show up in Chat History at all.
2. Copies the matching files from `chatSessions/` (the actual transcripts)
   and `chatEditingSessions/` (pending file-edit review state, if any)
   into the target.
3. Never touches source workspaces — everything is read-only there. Only
   the target's `state.vscdb` is ever written to, and it's backed up
   first automatically.

## Install

```bash
pip install -e .
```

This installs the `revive-chats` command.

## Usage

### Point at specific source workspaces

```bash
revive-chats /path/to/target/workspaceStorage/<hash> \
  "/path/to/source1/workspaceStorage/<hash>" \
  "/path/to/source2/workspaceStorage/<hash>"
```

### Create a fresh workspace automatically

```bash
revive-chats --name "revived chats" \
  "/path/to/source/workspaceStorage/<hash>"
```

This opens a new VS Code window for the folder, asks you to confirm
you've fully quit VS Code (required so `state.vscdb` isn't locked), then
auto-discovers the new workspace's hash and merges into it.

By default the new folder is created under `~/Desktop` — override with
`--base-dir`.

### Merge from every workspace on your machine

```bash
revive-chats --name "revived chats" --scan-all
```

Scans everything under `workspaceStorage` automatically instead of
listing sources by hand.

### Filter by date range

```bash
revive-chats --name "revived chats" --scan-all \
  --from 2026-01-01 --to 2026-06-30
```

Only sessions with a `lastMessageDate` inside this range (inclusive,
using your local timezone) are merged — both in the index and in the
copied files, so they always stay in sync.

### Skip the backup (not recommended)

```bash
revive-chats <target> <source> --no-backup
```

By default, the target's existing `state.vscdb` is backed up to
`state.vscdb.backup` (same folder, overwritten each run) before anything
is written.

## Requirements

- macOS/Linux/Windows with Python 3.10+
- The `code` CLI command available on PATH for `--name` (Command Palette
  → "Shell Command: Install 'code' command in PATH" if missing)

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Limitations

- `GitHub.copilot-chat/` (generic extension state, not session-specific)
  is copied only when no date filter is active, since it can't be
  attributed to a particular date range.
- This merges the raw internal storage format VS Code already
  understands — it does not use the Copilot Chat extension's own
  export/import feature, which uses a different (lossier) JSON shape.
- Always fully quit VS Code before running against a live target
  workspace — writing to `state.vscdb` while VS Code has it open will
  fail or risk corrupting the file.
