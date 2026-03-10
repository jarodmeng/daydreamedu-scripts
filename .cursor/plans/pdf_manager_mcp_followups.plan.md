---
name: pdf manager MCP followups
overview: Follow-up proposal for hardening the `pdf_file_manager` MCP utility after the core wrapper/server implementation is complete.
todos:
  - id: tool-metadata
    content: Add FastMCP tool metadata such as descriptions, tags, and optional output schemas so tools are easier for agents to discover and use correctly.
    status: pending
  - id: readonly-mode
    content: Add a readonly-only server mode so safer agent deployments can expose inspection tools without any mutation capability.
    status: pending
  - id: real-fastmcp-validation
    content: Add a lightweight test that validates registration against a real FastMCP object, not only the fake server shim.
    status: pending
  - id: path-guardrails
    content: Add MCP-level guardrails for filesystem mutation tools so risky operations can be constrained to scan roots or explicit allowlists.
    status: pending
  - id: connection-docs
    content: Document how external MCP clients should connect to the server, with example config and transport guidance.
    status: pending
isProject: false
---

# PDF File Manager MCP Follow-up Proposal

## Why A Follow-up Proposal Exists

The core MCP work is complete:

- the manager surface is wrapped in structured tool handlers
- the FastMCP server boundary exists
- tests cover the wrapper and server registration
- current-facing docs now describe Python + MCP as the supported interfaces

What remains is not foundational architecture. It is productization, safety hardening, and agent ergonomics.

## Recommendation

Do not expand the utility further by default. Focus on the smallest set of changes that improve real-world agent reliability and deployment safety:

1. add richer FastMCP tool metadata
2. add a readonly-only server mode
3. add one real FastMCP registration test
4. add path guardrails for filesystem mutations
5. document client connection patterns

## Proposed Work

### 1. Tool Metadata

Current registration in `pdf_file_manager_mcp_server.py` binds handlers by name only. That is enough for mechanics, but weak for agent usability.

Add metadata for each tool:

- concise description
- category tags such as `readonly`, `mutation`, `filesystem`
- notes on risk for mutating tools
- optional explicit output schema where it materially improves interoperability

This should live near the registration layer, not inside the manager logic.

### 2. Readonly-only Server Mode

Right now the server registers all tool groups by default:

- read-only
- safe mutation
- filesystem mutation

That is convenient for local use, but unnecessarily broad for many agent contexts.

Add a mode that registers only the readonly group. This could be:

- a constructor flag such as `tool_mode="readonly" | "default" | "all"`
- or separate factory functions for readonly vs full server

The goal is to let deployments choose a smaller trust surface without forking the code.

### 3. Real FastMCP Registration Validation

The current tests use a fake server object for registration checks. That is a good unit seam, but it still leaves a small gap between fake registration and the real library boundary.

Add a lightweight test that:

- creates a real `FastMCP` object
- registers the tool groups
- asserts the expected tool names are present

This does not need to start a transport or run a long-lived process.

### 4. Path Guardrails For Filesystem Mutations

The filesystem mutation tools currently mirror manager behavior closely. That keeps the wrapper thin, but also means the MCP layer does not yet add policy protection for riskier file operations.

Potential guardrails:

- allow mutations only under configured scan roots
- allow explicit additional safe roots
- require exact opt-in for operations outside managed roots
- reject paths that traverse outside expected areas after resolution

This should be an MCP-layer policy, not a rewrite of core manager behavior.

### 5. Connection Documentation

The server is runnable, but external client setup is still implicit.

Add a short document covering:

- how to run the MCP server with `stdio`
- when to use HTTP transport
- example client config snippets
- how to point the server at a specific registry DB
- what tool groups are exposed by default
- which mode to use for readonly deployments once that exists

## Suggested Delivery Order

1. tool metadata
2. readonly-only mode
3. connection docs
4. real FastMCP registration test
5. path guardrails

This order improves agent usability quickly before moving into policy decisions for mutation safety.

## Risks

- Adding metadata is low risk.
- Readonly mode is low risk if implemented as additive registration control.
- Real FastMCP validation is low risk but may require tests to depend on the installed package.
- Path guardrails are medium risk because overly broad restrictions could break valid local workflows.
- Connection docs are low risk but should avoid promising client-specific behavior that has not been exercised.

## Expected Outcome

After these follow-ups, `pdf_file_manager` would move from “implemented MCP surface” to “safer and easier to operate MCP utility”:

- better tool discovery for agents
- safer deployment options
- stronger confidence at the actual FastMCP boundary
- clearer operational guidance for consumers
