# Device control (mouse, keyboard, shell, screenshot)

Eversilver inherits openhuman's full computer-use toolset. Every tool
lives under `src/eversilver/tools/impl/` and is wired into the agent's
tool catalog at session-build time (`tools/ops.rs::all_tools_with_runtime`).

## What's available

| Tool | Source | What it does | Gate |
|---|---|---|---|
| `MouseTool` | `tools/impl/computer/mouse.rs` | Native click/move/scroll via `enigo` + human-path trajectory (anti-detection) | `computer_control.enabled` |
| `KeyboardTool` | `tools/impl/computer/keyboard.rs` | Native key press / type-string | `computer_control.enabled` |
| `ShellTool` | `tools/impl/system/shell.rs` | Run any shell command inside the security sandbox (workspace-only, allowed_commands list) | always on |
| `ScreenshotTool` | `tools/impl/system/...` (vision) | Capture the active screen as base64 PNG | always on |
| `ImageInfoTool` | same | Inspect dimensions/format of a captured image | always on |
| `NodeExecTool` | `tools/impl/system/node_exec.rs` | Run a `node` script via the managed Node bootstrap | `node.enabled` |
| `NpmExecTool` | `tools/impl/system/npm_exec.rs` | Run an `npm` command in the workspace | `node.enabled` |
| `ShellScheduleTool` | `tools/impl/system/schedule.rs` | Schedule a recurring shell command (cron-style) | always on |
| `FileReadTool` / `FileWriteTool` / `EditFileTool` / `ApplyPatchTool` | `tools/impl/filesystem/*` | Read, write, line-edit, apply unified diffs | always on |
| `GlobSearchTool` / `GrepTool` / `ListFilesTool` | same | Pattern + content search across the workspace | always on |
| `GitOperationsTool` | `tools/impl/filesystem/git_operations.rs` | `git status`, `diff`, `add`, `commit`, `push`, etc. | always on |
| `RunTestsTool` / `RunLinterTool` | same | Invoke project's test + lint commands | always on |
| `ToolStatsTool` | `tools/impl/system/tool_stats.rs` | Per-tool success-rate tracking, surfaced back to the agent for self-improvement | `learning.enabled` + `learning.tool_tracking_enabled` |
| `UpdateCheckTool` / `UpdateApplyTool` | `tools/impl/system/update_*.rs` | Check for + apply Eversilver self-update | always on |
| Vision capture | `accessibility/capture.rs` | Cross-platform full-screen / focused-window screenshot used by ScreenshotTool | always on |
| Focus probe | `accessibility/focus.rs` | Read the focused window, app name, and selected text | always on |
| Paste + backspace | `accessibility/paste.rs` | Insert text into the focused text field | always on |

## How to enable

`scripts/configure-eversilver-llm.py` now sets these flags by default:

```toml
[computer_control]
enabled = true

[node]
enabled = true

[learning]
enabled = true
tool_tracking_enabled = true
```

After running configure + relaunching, the next `tool spec filter` log
line shows the new total — typically jumping from ~41 to ~63 tools
when device control comes online.

## How the agent uses them

The orchestrator and worker agents see these tools as standard
function-calling specs in their model request. For example, when Athena
decides to take a screenshot:

```jsonc
{
  "tool_calls": [{
    "function": { "name": "screenshot",
                  "arguments": "{\"region\":\"active_window\"}" }
  }]
}
```

The Rust core's `dispatch` routes that to `ScreenshotTool::execute`,
runs the platform capture, and returns the base64 PNG back in the
next agent turn.

## Safety — what to know before turning this on

1. **The agent can move your mouse and type into any focused field.**
   If a sensitive app has focus, the agent can act there. Eversilver
   surfaces every action through the security/approval layer
   (`src/eversilver/approval/`); review pending actions when prompted
   instead of blanket-approving.

2. **Shell commands run in the security sandbox.**
   `config.autonomy.allowed_commands` + `forbidden_paths` constrain
   `ShellTool`. The defaults are conservative (`git`, `npm`, `cargo`,
   `ls`, `cat`, `grep`, `find`, etc.); extend deliberately.

3. **No permission-prompt on macOS/Linux until first use.**
   On macOS the first mouse-move triggers a system Accessibility
   permission dialog. Grant it once; subsequent runs work silently.
   On Linux X11 the user running Eversilver needs DISPLAY access.

4. **Disable globally any time:**
   ```powershell
   # Add to config.toml under [computer_control]
   enabled = false
   ```
   Or re-run the configure script with a future `--no-computer-control`
   flag (TODO).

## What's still server-side (OpenFang)

OpenFang's `browser-hand`, `researcher-hand`, `collector-hand` agents
on the VPS have their *own* Chrome/Playwright stacks for web
automation. Those run on the VPS, not on this laptop, so they don't
collide with the local `MouseTool`/`KeyboardTool`. Eversilver dispatches
chat to OpenFang; OpenFang's hands run on the VPS; OpenFang returns
results. Eversilver's local mouse/keyboard tools handle anything that
needs to happen on the user's machine (open a file, switch apps, type
into VS Code, etc.).
