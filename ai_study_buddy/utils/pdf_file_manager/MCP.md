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

## Metadata and groups quick reference

When using MCP tools, keep these locations distinct:

- File-level metadata is in `pdf_files.metadata` (returned by file tools such as `pdf_get_file` and `pdf_find_files`).
- Group-level identity is in `file_groups` fields (`label`, `group_type`, `anchor_id`, `notes`) returned by `pdf_get_file_group` and `pdf_list_file_groups`.
- Per-member semantics are in `file_group_members.role` (returned in group member payloads).

For `doc_type='book'` files:

- `metadata.unit` is the per-file unit/chapter label.
- The shared book identity should be represented by a `group_type='book'` group `label`.

`pdf_update_metadata` merges metadata keys; it does not replace the full metadata object.

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
- The safe-mutation tools `pdf_link_goodnotes_template_for_file` and `pdf_link_goodnotes_templates_for_root` wrap GoodNotes template resolution plus linking. They may auto-fix `is_template=True` for an already-registered resolved template, but they do not auto-register a resolved template that only exists on disk.
