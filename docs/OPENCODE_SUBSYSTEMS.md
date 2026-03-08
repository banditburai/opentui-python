# OpenCode TypeScript — 38 Subsystems Checklist

Source: `opencode/packages/opencode/src/`

Status key: `[ ]` not started, `[~]` partial/in-progress, `[x]` done in Talaria

---

## Core Architecture

- [ ] **agent** (1 file) — Agent definitions (build, plan, explore, compact, title, summary, general), per-agent model/tools/permissions/temperature
- [ ] **session** (16 files) — Session lifecycle, conversation history, compaction markers, forking, archiving, slugs, diff tracking, sharing
- [ ] **project** (6 files) — Project/workspace bootstrapping, project instance management, initialization
- [ ] **control** (2 files) — Control flow and state management

## Communication & APIs

- [ ] **cli** (49 files) — Terminal UI, command palette, themes, dialogs, autocomplete, session tabs, markdown rendering
- [ ] **server** (17 files) — HTTP API via Hono (30+ REST endpoints: sessions, files, config, providers, MCP, permissions, PTY)
- [ ] **bus** (3 files) — Internal pub/sub event bus between subsystems
- [ ] **acp** (3 files) — Agent Client Protocol (JSON-RPC interface for opencode as ACP server)
- [ ] **lsp** (4 files) — Language Server Protocol (20 built-in servers, auto-spawn, diagnostics, hover, definitions, references)
- [ ] **mcp** (4 files) — Model Context Protocol (HTTP/SSE transport, OAuth 2.0 PKCE, prompts, resources, notifications)
- [ ] **command** (1 file) — Command registry, markdown-based custom commands, template substitution, agent/model override

## Authentication & Configuration

- [ ] **auth** (1 file) — OAuth, API keys, well-known tokens for multiple providers
- [ ] **config** (6 files) — TOML/env configuration parsing, multi-file config, validation
- [ ] **permission** (3 files) — ask/allow/deny rules, pattern-based wildcards, per-tool/per-agent permissions, doom-loop detection
- [ ] **env** (1 file) — Environment variable management and defaults

## AI & Provider Integration

- [ ] **provider** (31 files) — 20+ AI providers (OpenAI, Anthropic, Google, Azure, etc.), streaming, model metadata, cost tracking
- [ ] **control-plane** (10 files) — Control plane configuration and orchestration

## Tools

- [ ] **tool** (24 files) — 20 tool implementations: apply_patch, bash, edit, glob, grep, ls, read, write, todo, memory, delegate, question, webfetch, etc.
- [ ] **shell** (1 file) — Shell/bash integration, command execution, environment setup
- [ ] **pty** (1 file) — Pseudo-terminal for interactive commands
- [ ] **question** (1 file) — Interactive structured questions (multi-choice + free text) from agent to user

## File System & Data

- [ ] **file** (5 files) — File operations, watching (watchdog equivalent), gitignore awareness
- [ ] **patch** (1 file) — Unified diff parsing and application
- [ ] **format** (2 files) — Auto-format on file edit, configurable formatter per file extension
- [ ] **storage** (5 files) — SQLite database with Drizzle ORM, schema migrations
- [ ] **snapshot** (1 file) — Git-based file state tracking, track/patch/restore/revert, garbage collection
- [ ] **worktree** (1 file) — Git worktree management

## Extensibility

- [ ] **skill** (3 files) — SKILL.md discovery, multi-path search, URL download, slash command integration
- [ ] **plugin** (3 files) — NPM/file plugins, plugin hooks (tool.definition, permission.ask), auth plugins
- [ ] **ide** (1 file) — IDE integration layer

## Infrastructure & Utilities

- [ ] **util** (26 files) — Filesystem helpers, logging, formatting, git operations, process management, text truncation
- [ ] **global** (1 file) — Global paths (~/.opencode/), directory resolution
- [ ] **id** (1 file) — Identifier generation (session IDs, message IDs, etc.)
- [ ] **installation** (1 file) — Version management, update checking
- [ ] **flag** (1 file) — Feature flags
- [ ] **scheduler** (1 file) — Task scheduling and async coordination
- [ ] **share** (2 files) — Session sharing (opncd.ai integration)
- [ ] **bun** (2 files) — Bun runtime integration

---

## Talaria Coverage Summary

| Category | Subsystems | Covered | Gap |
|----------|-----------|---------|-----|
| Core Architecture | 4 | 0 | 4 |
| Communication & APIs | 7 | 0 | 7 |
| Auth & Config | 4 | 0 | 4 |
| AI & Providers | 2 | 0 | 2 |
| Tools | 4 | 0 | 4 |
| File System & Data | 6 | 0 | 6 |
| Extensibility | 3 | 0 | 3 |
| Infrastructure | 8 | 0 | 8 |
| **Total** | **38** | **0** | **38** |

Update checkboxes as Talaria implements each subsystem.
