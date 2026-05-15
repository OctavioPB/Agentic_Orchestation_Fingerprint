# ADR-003: code-server over a Custom Web IDE for the Candidate Sandbox

**Status**: Accepted
**Date**: 2026-05-14

## Context

The candidate sandbox must provide a browser-accessible development environment where candidates can:

- Read and edit Python files.
- Execute code in an integrated terminal.
- Communicate with sub-agents (DELTA, NOVA, ECHO) via a chat panel.
- Have all interactions captured as telemetry events.

The two candidate approaches were:

1. **code-server** (`codercom/code-server`) — VS Code running server-side, accessed via browser, distributed as a Docker image.
2. **Custom lightweight IDE** — a web application built on Monaco Editor (the VS Code editor component) with a custom terminal emulator (xterm.js) and a bespoke WebSocket backend.

## Decision

Use **code-server** (`codercom/code-server`).

## Reasoning

### Candidate familiarity
VS Code is the most widely used IDE among the target candidate population (data engineers, pipeline developers). Candidates already know keyboard shortcuts, file explorer ergonomics, and the extension ecosystem. A custom IDE introduces cognitive overhead that contaminates the signal — candidates spend time learning the tool rather than demonstrating orchestration cognition.

### Extension API for telemetry
code-server exposes the full VS Code extension API. We can write a `orchid-telemetry` VS Code extension that hooks into:
- `vscode.workspace.onDidChangeTextDocument` — for edit activity.
- `vscode.window.terminals` — for terminal I/O capture.
- `vscode.commands.registerCommand` — to intercept agent communication commands.

This gives us telemetry hooks without patching the IDE codebase.

### Docker-native distribution
The `codercom/code-server` Docker image is the canonical distribution. No build process required on our side for the base environment. We extend it with a single `FROM codercom/code-server` Dockerfile that adds Python, the workspace seed, and the telemetry extension.

### Maintenance surface
A custom web IDE would require maintaining Monaco, xterm.js, WebSocket session management, file system abstraction, and terminal PTY management — approximately 3,000–5,000 lines of custom infrastructure. code-server externalizes this entirely to the open-source maintainers (Coder Inc., with active development and security patching).

### Trade-off accepted: UI customization limits
code-server's UI cannot be restyled to match `BRAND.md`'s design system without significant effort (the VS Code webview workbench is not designed for external theming). We accept this: the sandbox is a functional tool, not a branding surface. Candidates understand they are in a VS Code environment.

## Consequences

**Enables:**
- Zero custom IDE development in Sprint 1.
- Full VS Code feature set for candidates from day one.
- Telemetry via the VS Code extension API (Sprint 2 deliverable).
- Community-maintained security patching of the base image.

**Forecloses:**
- Full BRAND.md styling of the sandbox UI.
- Sub-100ms cold start (code-server takes ~3–5s to load).
- Embedding the chat panel as a native first-class UI element (must be a VS Code webview panel or sidebar panel).

**Mitigations:**
- The chat panel will be implemented as a VS Code sidebar webview extension (Sprint 3), which integrates naturally with the VS Code UX paradigm.
