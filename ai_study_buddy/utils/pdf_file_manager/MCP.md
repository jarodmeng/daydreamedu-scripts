# pdf_file_manager MCP

This document describes how to run and connect to the `pdf_file_manager` MCP server.

## Server entrypoint

Run the server with:

```bash
python3 ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py --db /path/to/pdf_registry.db
```

If `--db` is omitted, the manager uses its normal default DB resolution.

## Tool modes

The server supports two tool exposure modes:

- `default`: registers readonly, safe mutation, and filesystem mutation tools
- `readonly`: registers readonly tools only

Example readonly launch:

```bash
python3 ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py \
  --db /path/to/pdf_registry.db \
  --tool-mode readonly
```

Use `readonly` when an agent only needs to inspect the registry and should not be able to mutate files, metadata, groups, or scan roots.

## Transports

### stdio

`stdio` is the default and is the best choice for most local MCP client integrations.

```bash
python3 ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py \
  --db /path/to/pdf_registry.db \
  --tool-mode readonly
```

### HTTP

Use HTTP when the client expects a networked MCP server process.

```bash
python3 ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py \
  --db /path/to/pdf_registry.db \
  --transport http \
  --host 127.0.0.1 \
  --port 9000 \
  --path /mcp
```

## Example client config

Example `stdio` style MCP client command:

```json
{
  "command": "python3",
  "args": [
    "ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py",
    "--db",
    "/path/to/pdf_registry.db",
    "--tool-mode",
    "readonly"
  ]
}
```

## Recommended defaults

- For general agent use: `--tool-mode readonly`
- For local maintenance workflows you trust: default tool mode
- Prefer `stdio` unless the client specifically benefits from HTTP transport

## Notes

- The MCP wrapper instantiates `PdfFileManager` per tool call.
- Tool responses are JSON-safe and use structured error payloads.
- Filesystem mutation tools are higher risk and should only be exposed when the client genuinely needs them.
- For GoodNotes folders (any path containing a `GoodNotes/` segment), `scan_for_new_files` and `compress_and_register` use `preserve_input=True` so originals are never renamed or moved; `_c_` mains are created alongside and linked as raw↔main. Use the `preserve_input` argument on `pdf_compress_and_register` when calling the tool directly.
- The readonly tool `pdf_resolve_goodnotes_template` resolves a GoodNotes main path to the corresponding DaydreamEdu `_c_` template/source path, following the naming rules in `docs/proposals/05-goodnotes-exam-registration.md`.
