# OpenCode Python (Talaria) — Architecture Decisions

## Three-Way Comparison: OpenCode TypeScript vs Hermes Agent vs Talaria

### Context

Talaria is a Python AI coding agent that draws from two reference implementations:
- **OpenCode** (TypeScript, 33 subsystems, production TUI) — polished UI, git snapshots, LSP, permissions
- **Hermes Agent** (Python, 50k LOC, battle-tested) — multi-platform, skills, context compression, interrupt-aware loop

Talaria is at **Phase 3b** (config, agent loop, session, compression, approval, tool registry all working, 78 tests passing). This document decides the best approach for each remaining subsystem, producing a decision matrix that guides implementation through Phases 4-10.

### How to Read This Document

For each of the ~19 remaining subsystems:

1. **How OpenCode does it** — pattern, key files, strengths
2. **How Hermes does it** — pattern, key files, strengths
3. **Talaria recommendation** — which approach (or hybrid), rationale, key design decisions
4. **Talaria sketch** — module path, key classes/functions, integration points with existing code

---

## Tier 1: Core Agent Functionality

### 1.1 Missing Tools (edit, glob, grep, task, todo, question, ls)

**OpenCode:** 20 tool files, each a standalone module. Tool registry with per-tool permissions. Tools have `metadata` (description, parameters via Zod schema) + `execute` function. Supports truncation (large outputs stored to file, summary returned).

**Hermes:** 35 tools via `registry.register()` self-registration at import. Tools are functions decorated or explicitly registered. `model_tools.py` imports all modules to trigger discovery. Special tools (todo, memory, delegate_task) handled inline in agent loop because they need state access.

**Talaria already has:** `@tool` decorator, `ToolRegistry` with `dispatch()`, `ToolSpec` dataclass, OpenAI schema generation. File read/write/patch, terminal, todo, memory tools exist.

**Decision: Hermes pattern (already adopted) + OpenCode's tool completeness**

Talaria's `@tool` decorator pattern is cleaner than both. Keep it. Add missing tools as individual modules in `opencode/ai/tools/`:

| Tool | Module | Notes |
|------|--------|-------|
| `edit` | `tools/edit.py` | Exact string replacement (OpenCode pattern — critical for LLM editing) |
| `glob` | `tools/glob.py` | File pattern matching (stdlib `glob` + `pathlib`) |
| `grep` | `tools/grep.py` | Content search — subprocess `rg` if available, fallback to `re` |
| `task` | `tools/delegate.py` | Subagent delegation (Hermes `delegate_tool` pattern — spawn child AIAgent) |
| `question` | `tools/question.py` | Ask user structured questions (OpenCode pattern — multi-choice + free text) |
| `ls` | `tools/ls.py` | Directory listing with gitignore awareness |
| `webfetch` | `tools/webfetch.py` | URL content extraction (Hermes `web_extract` pattern) |

**Key decision:** OpenCode's `edit` tool (exact string replacement) is better than Hermes's `patch` tool (unified diff). LLMs are more reliable with find-and-replace than generating diffs.

---

### 1.2 Permission System

**OpenCode:** Complex — `ask`/`allow`/`deny` with pattern-based wildcard rules, per-tool and per-agent permissions, session-scoped approval, plugin hooks, doom-loop detection. ~3 files, 1000+ LOC.

**Hermes:** Pragmatic — `approval.py` with 28 dangerous command regex patterns, per-session thread-safe approval state (once/session/always/deny), interactive CLI prompt with timeout. ~200 LOC.

**Talaria already has:** `tools/approval.py` with 20+ patterns, per-session state, interactive prompting — essentially the Hermes pattern.

**Decision: Hermes base (already have) + OpenCode's per-tool permission layer**

Keep Talaria's existing `approval.py` for dangerous command detection. Add a thin permission layer on top:

```
opencode/permissions.py
- PermissionRule(tool_pattern, path_pattern, action: ask|allow|deny)
- PermissionManager — loads rules from config, checks before tool dispatch
- Session-scoped "always allow" cache
```

**Skip:** OpenCode's plugin hooks, doom-loop detection, PermissionNext complexity. Add later if needed.

---

### 1.3 Agent System (build/plan/explore/compaction/title agents)

**OpenCode:** Agent definitions with per-agent model, tool access, permissions, temperature, step limits, custom prompts. 7 built-in agents (build, plan, explore, compaction, title, summary, general). Custom agents via `.opencode/agents/*.md`.

**Hermes:** Single agent class but with toolset filtering (enabled/disabled toolsets per invocation). `delegate_tool` spawns child AIAgent with restricted toolsets. No formal agent types.

**Talaria already has:** `AIAgent` class with `enabled_toolsets`/`disabled_toolsets`. Similar to Hermes.

**Decision: OpenCode's agent concept + Hermes's simplicity**

Don't create 7 agent classes. Instead, agent "profiles" as config:

```
opencode/agents.py
- AgentProfile(name, model, tools, system_prompt, max_steps, temperature)
- BUILTIN_PROFILES = {
    "build": AgentProfile(tools=ALL, ...),
    "plan": AgentProfile(tools=READ_ONLY, ...),
    "explore": AgentProfile(tools=["read", "glob", "grep"], max_steps=20, ...),
    "compact": AgentProfile(model=SMALL_MODEL, tools=[], ...),
    "title": AgentProfile(model=SMALL_MODEL, tools=[], max_steps=1, ...),
  }
- load_custom_agents(path) — loads .opencode/agents/*.md or .talaria/agents/*.md
```

`AIAgent` gets an `agent_profile` parameter. The profile constrains tools and model. Subagent spawning (task tool) picks the appropriate profile.

---

### 1.4 Compaction / Context Management

**OpenCode:** Auto-compaction when context near capacity. Pruning removes old tool outputs. Specialized compaction agent generates summaries. Protected tools preserved during pruning.

**Hermes:** `context_compressor.py` — protect first 3 + last 4 turns, summarize middle via Gemini Flash (auxiliary client). Compression triggers new session with parent_session_id link.

**Talaria already has:** `ContextCompressor` with protect-head/tail, auxiliary model summarization, threshold-based triggering. Very close to Hermes.

**Decision: Keep Talaria's existing compressor + add OpenCode's pruning**

Add tool output pruning before full compression. When approaching threshold:
1. First pass: prune old tool outputs (replace with "[output truncated]")
2. If still over threshold: full compression via auxiliary model

Add to existing `context_compressor.py`:
```python
def prune_tool_outputs(self, messages, keep_last_n=5) -> list[dict]:
    """Replace old tool result content with truncated summaries."""
```

---

## Tier 2: Reliability & UX

### 2.1 Snapshot / Revert System

**OpenCode:** Separate git repo for tracking file state. Track/patch/restore/revert operations. Periodic garbage collection.

**Hermes:** No snapshot system. Relies on user's git.

**Talaria has:** Nothing.

**Decision: OpenCode's approach, simplified**

```
opencode/snapshot.py
- SnapshotManager(project_dir)
- track() -> snapshot_id — capture current file state (git stash-like)
- diff(snapshot_id) -> list[FileDiff] — what changed since snapshot
- restore(snapshot_id, files=None) — restore specific files or all
- cleanup(older_than_days) — garbage collect old snapshots
```

Implementation: Use a hidden git repo in `.talaria/snapshots/` (same as OpenCode). Take snapshots before tool execution (especially write/edit/shell). This enables undo.

---

### 2.2 Retry / Error Handling

**OpenCode:** Auto-retry on retryable API errors. Context overflow triggers compaction. Abort/cancel support via AbortController.

**Hermes:** Tenacity for API retries (exponential backoff 2s->4s->8s). Invalid tool name retry (3x). Invalid JSON retry (3x). Incomplete scratchpad retry (2x). Max iterations exit.

**Talaria already has:** Basic tool calling loop with max_iterations. No retry logic.

**Decision: Hermes patterns (tenacity + in-loop retries)**

Add to `agent.py`:
```python
# API call retry (tenacity)
@retry(wait=wait_exponential(min=2, max=30), stop=stop_after_attempt(3),
       retry=retry_if_exception_type(TRANSIENT_ERRORS))
async def _call_llm(self, messages, tools): ...

# In-loop retries
INVALID_TOOL_RETRIES = 3
INVALID_JSON_RETRIES = 3
```

Add abort support: `self._abort = asyncio.Event()` checked between tool calls.

---

### 2.3 Instruction Files

**OpenCode:** Loads AGENTS.md, .opencode instructions, skills into system prompt. Multiple search paths.

**Hermes:** Loads SOUL.md (persona), AGENTS.md (project instructions), .cursorrules, .cursor/rules/*.mdc. Hierarchical composition. 20KB cap with smart truncation. Prompt injection scanning.

**Talaria already has:** `prompt_builder.py` exists but details weren't fully explored.

**Decision: Hermes pattern (hierarchical, with injection scanning)**

```
opencode/instructions.py
- load_instructions(cwd) -> str
  - Search: AGENTS.md, .talaria/instructions.md, .opencode/instructions.md, .cursorrules
  - Hierarchical: walk up to repo root, combine
  - Cap at 20KB
  - Scan for prompt injection before including
```

---

### 2.4 Session Enhancements

**OpenCode:** Forking, archiving, slugs, diff tracking, sharing, versioning, plans, export, compaction markers.

**Hermes:** Session splitting on compression (parent_session_id), FTS5 search with Gemini Flash summarization, source tracking (cli/telegram/etc.), export as JSONL.

**Talaria already has:** Full SQLite session store with FTS5 search, parent_session_id, source tracking, export. Very close to Hermes.

**Decision: Add OpenCode's forking + archiving to existing Talaria sessions**

Add to `session.py`:
```python
def fork_session(self, session_id, from_message_id) -> str: ...
def archive_session(self, session_id) -> None: ...
def unarchive_session(self, session_id) -> None: ...
```

Skip: sharing (opncd.ai specific), plans (can add later), versioning.

---

## Tier 3: Extensibility

### 3.1 Skill System

**OpenCode:** SKILL.md files with YAML frontmatter. Discovery across multiple paths (.opencode/skills/, .claude/skills/). URL-based skill download. Skills as slash commands. Skill tool for AI invocation.

**Hermes:** Agent-created skills (procedural memory). SKILL.md format. Skills Hub with multiple sources (GitHub, ClawHub, LobeHub). Security scanning (skills_guard.py — exfiltration, injection, destructive commands). Trust levels. Quarantine. Audit log.

**Talaria already has:** Nothing, but Phase 8 in the roadmap.

**Decision: Hermes's agent-created skills + OpenCode's discovery paths**

Hermes's key insight: the agent creates skills for itself when it encounters complex multi-step tasks. This is more valuable than a static skill library.

```
opencode/skills/
  __init__.py       — SkillManager (discover, load, search)
  discovery.py      — Search paths (.talaria/skills/, .opencode/skills/, ~/.config/talaria/skills/)
  guard.py          — Security scanning (Hermes skills_guard pattern)

opencode/tools/skill.py — Tools: skill_create, skill_edit, skill_list, skill_view
```

---

### 3.2 Command System

**OpenCode:** Built-in commands (init, review). Custom via .opencode/commands/*.md. MCP prompts as commands. Template substitution ($1, $ARGUMENTS). Agent/model override per command.

**Hermes:** Slash commands in CLI (`/model`, `/tools`, `/session`, `/memory`, etc.) defined in `hermes_cli/commands.py`. No markdown-based custom commands.

**Talaria already has:** CLI with slash commands (from Hermes pattern).

**Decision: OpenCode's markdown commands + existing slash commands**

```
opencode/commands.py
- load_commands(cwd) -> dict[str, Command]
  - Built-in: /init, /review, /compact, /model, /session
  - Custom: .talaria/commands/*.md, .opencode/commands/*.md
  - Template substitution
```

---

### 3.3 Plugin System

**OpenCode:** NPM plugins. File plugins (.opencode/plugins/*.{ts,js}). Plugin hooks (tool.definition, permission.ask). Built-in auth plugins.

**Hermes:** No formal plugin system. Extensibility via tool modules, event hooks (YAML), and custom skill sources.

**Decision: Python entry points (Phase 5 in Talaria roadmap)**

```
opencode/plugins.py
- discover_plugins() — via importlib.metadata entry_points(group="talaria.plugins")
- PluginHook(on_tool_call, on_permission, on_message)
- load_file_plugins(path) — .talaria/plugins/*.py
```

This is the most Pythonic approach. Skip npm-style complexity.

---

### 3.4 MCP Enhancements

**OpenCode:** HTTP transport (StreamableHTTP, SSE), OAuth 2.0 with PKCE, prompts, resources, notifications, credential storage.

**Hermes:** No MCP support.

**Talaria has:** Nothing for MCP (opentui-python has an MCP client, but Talaria doesn't).

**Decision: Port from opentui-python's MCP client + add OpenCode's HTTP transport**

```
opencode/mcp/
  client.py   — MCPClient (stdio + HTTP transports)
  auth.py     — OAuth 2.0 for remote MCP servers
  tools.py    — Adapt MCP tools to ToolRegistry
```

Start with stdio (already built in opentui-python). Add HTTP transport later.

---

## Tier 4: Polish

### 4.1 TUI (if Talaria gets a TUI)

**OpenCode:** Full OpenTUI-based TUI with 20+ dialogs, 30+ themes, command palette, autocomplete, session tabs.

**Hermes:** prompt_toolkit-based CLI with rich output. No full TUI.

**Decision: Defer TUI decisions**

Talaria's CLI (prompt_toolkit + rich) is sufficient for now. If a TUI is needed later, use opentui-python as the rendering layer (it's in the same repo). This is Phase 4+ territory.

---

### 4.2 LSP Integration

**OpenCode:** 20 built-in LSP servers. Auto-spawn per file extension. Diagnostics, hover, definition, references.

**Hermes:** No LSP.

**Decision: Defer, add as optional package**

LSP is valuable but complex. Add as `talaria-lsp` optional package in Phase 10. Start with diagnostics-only (most impactful for code quality feedback to the agent).

---

### 4.3 Formatter

**OpenCode:** Auto-format on file edit. Configurable command per file extension.

**Hermes:** No auto-format.

**Decision: Simple, add to file write tool**

```python
# In tools/file.py, after write:
if config.formatter.enabled:
    fmt_cmd = config.formatter.get_command(file_ext)
    if fmt_cmd:
        subprocess.run(fmt_cmd.replace("$FILE", path), shell=True, timeout=10)
```

---

### 4.4 Server Routes

**OpenCode:** 30+ REST endpoints covering sessions, files, config, providers, MCP, permissions, PTY.

**Hermes:** Gateway server for messaging platforms, no REST API for the agent itself.

**Decision: Defer to Phase 6 (Gateway)**

REST API should come with the gateway package. Not needed for CLI-only usage.

---

## Unique Hermes Innovations to Adopt

These don't map to OpenCode subsystems but are high-value Hermes patterns:

### H.1 Interrupt-Aware Agent Loop
User can interrupt mid-execution. Current tool calls skipped, new message queued.
Add to `agent.py`: `interrupt()` method, checked between tool calls.

### H.2 Programmatic Tool Calling (Code Execution Sandbox)
Agent writes Python that calls tools via RPC. Collapses multi-step pipelines into single turn.
Add as `tools/code_execution.py` — Unix socket RPC, stripped environment.

### H.3 FTS5 Session Search Tool
Search entire conversation history with snippet extraction + summarization.
Already in Talaria's `session.py`. Add as a tool in `tools/session_search.py`.

### H.4 Memory Nudges
Periodic reminders to use memory/skill tools for multi-session continuity.
Add to `prompt_builder.py`: inject nudge every N turns.

---

## Implementation Order

Based on dependencies and impact:

| Phase | Subsystems | Depends On |
|-------|-----------|------------|
| **4a** | Missing tools (edit, glob, grep, ls) | Existing tool registry |
| **4b** | Retry/error handling, instruction files | Agent loop |
| **4c** | Agent profiles (build/plan/explore) | Tools, config |
| **4d** | Task delegation tool, question tool | Agent profiles |
| **5a** | Permission layer | Tool dispatch |
| **5b** | Snapshot/revert | File tools |
| **5c** | Compaction pruning | Existing compressor |
| **5d** | Session enhancements (fork, archive) | Existing sessions |
| **6** | Skill system | Tools, config |
| **7** | Command system | Skills, CLI |
| **8** | Plugin system (entry points) | All core |
| **9** | MCP client | Tool registry |
| **10** | TUI, LSP, formatter, server | Everything |

---

## Files to Create (Summary)

| File | Purpose | Priority |
|------|---------|----------|
| `tools/edit.py` | Exact string replacement tool | 4a |
| `tools/glob.py` | File pattern matching tool | 4a |
| `tools/grep.py` | Content search tool | 4a |
| `tools/ls.py` | Directory listing tool | 4a |
| `instructions.py` | Instruction file loading | 4b |
| `agents.py` | Agent profiles | 4c |
| `tools/delegate.py` | Subagent task delegation | 4d |
| `tools/question.py` | Structured user questions | 4d |
| `permissions.py` | Permission rules layer | 5a |
| `snapshot.py` | Git-based file snapshots | 5b |
| `tools/webfetch.py` | URL content extraction | 6 |
| `skills/__init__.py` | Skill manager | 6 |
| `skills/discovery.py` | Skill discovery | 6 |
| `skills/guard.py` | Skill security scanning | 6 |
| `commands.py` | Command system | 7 |
| `plugins.py` | Plugin system | 8 |
| `mcp/client.py` | MCP client | 9 |

All paths relative to `src/opencode/`.

---

## Decision Summary

| Subsystem | Pattern Source | Rationale |
|-----------|--------------|-----------|
| Tool modules | Hermes `@tool` | Already adopted, cleaner than both |
| Edit tool | **OpenCode** | Find-replace > unified diff for LLMs |
| Permissions | Hermes base + **OpenCode** layer | Pragmatic base, extensible top |
| Agent profiles | **OpenCode** concept, Hermes impl | Config-driven profiles, single AIAgent class |
| Compaction | Hermes base + **OpenCode** pruning | Two-pass: prune first, compress if needed |
| Snapshots | **OpenCode** | Hidden git repo for undo |
| Retry | **Hermes** | Tenacity + in-loop retries |
| Instructions | **Hermes** | Hierarchical, injection-scanned |
| Sessions | Hermes base + **OpenCode** extras | Fork/archive on top of existing store |
| Skills | **Hermes** agent-created + OpenCode paths | Agent procedural memory is key insight |
| Commands | **OpenCode** markdown + existing CLI | Markdown-based custom commands |
| Plugins | Neither — **Python entry points** | Most Pythonic approach |
| MCP | Port existing + **OpenCode** HTTP | Start stdio, add HTTP later |
| TUI | **Defer** | CLI sufficient for now |
| LSP | **Defer** | Optional package later |
| Formatter | **OpenCode** (simplified) | Post-write hook |
| Server | **Defer** | Phase 6 gateway |
| Interrupts | **Hermes** | Unique innovation |
| Code execution | **Hermes** | Tool RPC sandbox |
