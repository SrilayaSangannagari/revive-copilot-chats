# 🩺 Revive copilot chats

**Recovers Copilot Chat history that VS Code can no longer reach.**

Chat sessions vanish from the Chat History panel when:

- 📁 a project folder is **moved**, **renamed**, or **deleted**
- 🚪 a workspace is **closed without saving**

The chats are still on your disk — VS Code just can't find them any
more. `revive-chats` collects them into a new folder you can open, so
they show up in the Chat History panel again.

---

## 📦 Install

Nothing to clone:

```bash
pip install git+https://github.com/SrilayaSangannagari/revive-copilot-chats.git
```

Or with [pipx](https://pipx.pypa.io), which keeps it in its own
environment instead of your system Python:

```bash
pipx install git+https://github.com/SrilayaSangannagari/revive-copilot-chats.git
```

Either way you get the `revive-chats` command.

## ✅ Before you run it

| | Why it matters |
|---|---|
| **Python 3.10+** | Required to install the tool. |
| **The `code` command on your PATH** | The tool uses it to create the new workspace. Missing? In VS Code: Command Palette (`Cmd+Shift+P`) → *Shell Command: Install 'code' command in PATH*. |
| **Use a normal terminal — not VS Code's built-in one** | The tool needs VS Code fully closed partway through, which you can't do from inside it. |
| **Be ready to quit VS Code** | It will ask you to. See step 2 below. |

## 🚀 Quick start

```bash
revive-chats --name "revived chats"
```

Then follow along — the tool pauses and waits for you in the middle:

1. **A new VS Code window opens** for the folder it just created
   (`~/Desktop/revived chats`). This only registers the folder with VS
   Code. You don't need to do anything in the window.

2. **Fully quit VS Code** — `Cmd+Q`, not just closing the window. VS
   Code keeps a lock on the file this tool has to write to.

3. **Return to your terminal** and answer `yes`:

   ```
   Have you fully quit VS Code? (yes/no): yes
   ```

4. **Wait for `Done.`** It usually takes a second or two.

5. **Open that folder in VS Code** and look at the Chat History panel —
   your recovered chats are there.

## 🎛️ Other ways to run it

**Only chats from a date range** — recommended, since recovering
everything pulls from every project you've ever opened:

```bash
revive-chats --name "q1 chats" --from 2026-01-01 --to 2026-06-30
```

Both dates are inclusive, in your local timezone, and either one works
on its own.

**Put the new folder somewhere other than the Desktop:**

```bash
revive-chats --name "revived chats" --base-dir ~/projects
```

**Recover from one specific workspace** instead of scanning them all:

```bash
revive-chats --name "revived chats" \
  "$HOME/Library/Application Support/Code/User/workspaceStorage/<hash>"
```

## ⚠️ Cautions



**1. Always recover into the same folder.**

Pick one recovery workspace and reuse it. Recovering into a second
folder won't create duplicates *inside* either one, but you end up with
the same chats living in two places — double the disk space.

**2. Chat in the original workspace — treat the revived one as read-only.**

Read, search, and copy from the revived workspace as much as you like.
But to *continue* a chat, go back to the project it came from.

Your original workspaces always win. Anything you type inside the revived
workspace is **overwritten on the next recovery**, because the original's
copy of that chat is copied straight over it.

Your original chats are safe either way. The tool only ever reads from
them, never writes.

## 🛠️ Options

| Flag | What it does |
|---|---|
| `--name "folder name"` | Create a fresh workspace with this name and merge into it. |
| `--base-dir <path>` | Where `--name` puts the folder. Default: `~/Desktop`. |
| `--from YYYY-MM-DD` | Only chats whose last message is on or after this date. |
| `--to YYYY-MM-DD` | Only chats whose last message is on or before this date. |

Run `revive-chats --help` for the full list, including a few advanced
flags.

## 🩹 Troubleshooting

| Problem | Fix |
|---|---|
| `code: command not found`, or the tool says it can't open VS Code | Install the shell command: Command Palette → *Shell Command: Install 'code' command in PATH*. |
| `Could not write to ... Is VS Code currently open?` | VS Code wasn't fully quit. Quit it with `Cmd+Q` and run the command again. |
| `ERROR: this command needs to ask a yes/no question interactively` | You piped the command or ran it in a script. Run it directly in a terminal. |
| It finished, but Chat History is empty | Make sure you opened **the folder the tool created**, not your original project. The path is on the last line of the output. |
| `Target now has 0 indexed session(s)` | Nothing matched. If you used `--from`/`--to`, try widening or dropping the dates. |
| I want to undo the merge | Restore `state.vscdb.backup` from the target folder, next to `state.vscdb`. |

## 🔍 What it touches

- **Your sources are read-only.** Nothing you recover *from* is changed.
- **One file gets written:** the target's `state.vscdb`. It is copied to
  `state.vscdb.backup` first — same folder, overwritten on each run, so
  keep your own copy if an earlier run matters to you.
- **Files are copied** from `chatSessions/`, `chatEditingSessions/`, and
  `GitHub.copilot-chat/`. Your original workspaces are the source of
  truth: if a chat changed since the last recovery, the revived copy is
  replaced with the current one.
- **Re-running into the same folder is safe.** Nothing is duplicated —
  each chat appears once, taken from its most recently updated copy.

<details>
<summary>Why the chats go missing in the first place</summary>

VS Code stores chats in `workspaceStorage/<hash>/`, where `<hash>` is
derived from your project folder's path. Move, rename, or delete that
folder and the hash stops matching anything, so nothing points at the
chats. An unsaved workspace is the same story from the other end — it
never had a stable path to derive a lasting hash from. Either way the
chats sit there fully intact, just unreachable.

This tool merges the index entry that lists those chats — plus their
files — into a workspace VS Code *can* still see.

</details>
