# Memory (Obsidian) & MCP integration

## Memory → Obsidian

Eversilver's memory tree ships with full Obsidian-compatible markdown
output. Every chunk lands as one `.md` file under `<content_root>` with
YAML front-matter (`tags`, `aliases`, `children` as Obsidian
wikilinks). The folder layout is what `obsidian.rs` enforces:

```
<content_root>/
├── .obsidian/                           # auto-generated workspace marker
├── raw/                                 # verbatim source bytes
│   ├── email/<participants>/<chunk_id>.md
│   ├── chat/<source_slug>/<chunk_id>.md
│   └── document/<source_slug>/<chunk_id>.md
└── wiki/                                # processed, human-facing
    └── summaries/
        ├── source-<scope_slug>/L<level>/<id>.md
        ├── global-<yyyy-mm-dd>/L<level>/<id>.md
        └── topic-<scope_slug>/L<level>/<id>.md
```

### Wiring it to your existing vault

The configure script now sets `memory_tree.content_dir` per-user. The
default points at the canonical vault location:

```
%USERPROFILE%\OneDrive\Documents\Obsidian Vault\Eversilver
```

Override with the `--obsidian-vault` flag:

```powershell
# Custom vault location
python scripts\configure-eversilver-llm.py --obsidian-vault "D:\Notes\Eversilver"

# Disable Obsidian wiring (chunks land under <workspace>/memory_tree/content)
python scripts\configure-eversilver-llm.py --obsidian-vault off
```

Opening the vault in Obsidian:

1. Launch Obsidian → "Open folder as vault" → select the configured
   path (one level above the `Eversilver/` subfolder if you want all
   notes in one vault; or the `Eversilver/` folder itself for an
   Eversilver-only vault).
2. Eversilver's running. Send any chat or pull any data — the chunk
   appears as a `.md` file with the right front-matter.
3. Obsidian's Graph View immediately picks up the wikilinks between
   chunks.

The dim-1024 embedder (`bge-m3` via local Ollama, configured in the
same pass) is what powers semantic search across the vault from inside
the Eversilver agent.

## MCP

There are two MCP roles. They're different products:

### Eversilver as an MCP **server**

Eversilver exposes its own tool catalog as MCP over stdio. Run:

```
eversilver mcp
```

Other MCP-aware clients (Claude Desktop, Claude Code, OpenFang, …)
can plug this in to get access to Eversilver's local skills, memory
tree reads, and config getters. The mapping lives in
`src/eversilver/mcp_server/`.

### MCP **client** support (calling external MCP servers)

Eversilver itself has **no built-in MCP client.** External MCP
servers (laptop-mcp, fetch, github, sqlite-mcp, etc.) aren't reachable
from Eversilver's agent loop directly.

**OpenFang on the Athena VPS IS an MCP client.** The chat path is:

```
Eversilver chat panel
   └─► OpenFang /v1/chat/completions (model=Athena)
         └─► Athena agent
               └─► OpenFang MCP client (configured in ~/.openfang/openfang.toml)
                     └─► laptop-mcp, github-mcp, sqlite-mcp, …
```

So "make laptop-mcp work" means **edit OpenFang's `config.toml` on the
VPS**. Add a `[[mcp_servers]]` block. Two transports are supported —
stdio (local subprocess) and SSE (remote HTTP):

```toml
# ~/.openfang/openfang.toml  on the Athena VPS

# Example: SAGE swarm's laptop_agent at :11441 over HTTP/SSE
[[mcp_servers]]
name         = "laptop-mcp"
timeout_secs = 30

[mcp_servers.transport]
type = "sse"
url  = "http://localhost:11441/mcp"

# Example: official GitHub MCP via npx
[[mcp_servers]]
name         = "github"
timeout_secs = 30
env          = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

[mcp_servers.transport]
type    = "stdio"
command = "npx"
args    = ["-y", "@modelcontextprotocol/server-github"]

# Example: SQLite query/manage
[[mcp_servers]]
name         = "sqlite-mcp"
timeout_secs = 30

[mcp_servers.transport]
type    = "stdio"
command = "uvx"
args    = ["mcp-server-sqlite", "--db-path", "/var/lib/openfang/state.db"]
```

After editing, restart OpenFang on the VPS:

```bash
ssh athena 'sudo systemctl restart openfang'
# or whatever your supervisor uses
```

Confirm the agents see the tools:

```bash
curl -H "Authorization: Bearer $OPENFANG_API_KEY" \
     http://62.171.154.39:4200/api/skills
# Should now list each MCP server's tools
```

Once OpenFang knows the MCP server, every running agent (Athena,
researcher, browser-hand, …) gets the tools automatically. Eversilver
doesn't need any further changes.

### Why the laptop-mcp isn't reaching you today

`laptop_agent.py` (the SAGE swarm's file/git/shell tool server) runs
on **your laptop** at `localhost:11441`, not on the VPS. OpenFang on
the VPS can't reach `localhost:11441` because that's *your* localhost.
Either:

1. **Move laptop_agent to the VPS** so it lives next to OpenFang, or
2. **Expose your local :11441 to the VPS** via a tunnel (ngrok,
   cloudflared, tailscale) and point OpenFang at the public URL, or
3. **Add laptop-mcp as a stdio server on the VPS** with the same
   capabilities (file/git/shell tools running on the VPS rather than
   reaching back to your machine — usually the intent for an OS-level
   agent anyway).

Option (3) is the cleanest for a "personal AI OS" deployment: the
agent runs where its tools run.
