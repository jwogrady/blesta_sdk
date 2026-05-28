# MCP Server Usage Reference

`blesta_sdk.mcp` exposes the full Blesta API surface as an
[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server. This lets
Claude, Cursor, and other MCP-compatible AI tools query, paginate, and introspect a
Blesta billing instance directly.

## Requirements

- Python 3.10+
- `pip install blesta_sdk[mcp]`

## Credentials

Set the following environment variables before starting the server:

| Variable | Required | Description |
|----------|----------|-------------|
| `BLESTA_API_URL` | Yes | API base URL (e.g. `https://billing.example.com/api`) |
| `BLESTA_API_USER` | Yes | API username |
| `BLESTA_API_KEY` | Yes | API key |
| `BLESTA_AUTH_METHOD` | No | `basic` (default) or `header` |
| `BLESTA_ALLOW_HTTP` | No | `true` to permit `http://` URLs (local/dev only) |

Credentials are read **at call time** — you can restart the server with different env vars
to point at a different Blesta instance.

A `.env` file in the working directory is automatically loaded at startup if `python-dotenv`
is installed (`pip install blesta_sdk[cli]` or `pip install python-dotenv`).

## Starting the Server

```bash
blesta-mcp
```

Or via Python:

```bash
python -m blesta_sdk.mcp.server
```

The server runs over stdio (the MCP standard for local tool integrations).

## Client Configuration

### Claude Code

Add to your project's `.claude/settings.json` or user-level MCP config:

```json
{
  "mcpServers": {
    "blesta": {
      "command": "blesta-mcp",
      "env": {
        "BLESTA_API_URL": "https://billing.example.com/api",
        "BLESTA_API_USER": "api_user",
        "BLESTA_API_KEY": "api_key"
      }
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "blesta": {
      "command": "blesta-mcp",
      "env": {
        "BLESTA_API_URL": "https://billing.example.com/api",
        "BLESTA_API_USER": "api_user",
        "BLESTA_API_KEY": "api_key"
      }
    }
  }
}
```

---

## Tools

All tools return JSON strings. Successful calls include `"ok": true`; failures include
`"ok": false` and an `"errors"` or `"error"` key.

### `blesta_call`

Invoke a single Blesta API method.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `model` | string | required | Model name (e.g. `"Clients"`) |
| `method` | string | required | Method name (e.g. `"getList"`) |
| `params` | string | `"{}"` | JSON-encoded parameter dict |
| `action` | string | `null` | HTTP method override: `GET`, `POST`, `PUT`, or `DELETE` |

**Example:**

```
blesta_call(model="Clients", method="getList", params='{"status": "active"}')
```

**Response:**

```json
{"ok": true, "data": [{"id": 1, "firstname": "Alice", ...}]}
```

---

### `blesta_get_all`

Paginate a list endpoint and return all records.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `model` | string | required | Model name |
| `method` | string | required | List method name |
| `params` | string | `"{}"` | JSON-encoded parameter dict |
| `max_pages` | int | `null` | Optional page limit |

**Response:**

```json
{"ok": true, "count": 142, "data": [...]}
```

---

### `blesta_extract`

Fetch multiple paginated endpoints in a single call.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `targets` | string | JSON array of `[model, method]` or `[model, method, params]` tuples |

**Example:**

```
blesta_extract(targets='[["Clients", "getList"], ["Invoices", "getList", {"status": "unpaid"}]]')
```

**Response:**

```json
{
  "ok": true,
  "data": {
    "Clients.getList": [...],
    "Invoices.getList": [...]
  }
}
```

---

### `blesta_count`

Fetch a record count from a Blesta count method.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `model` | string | required | Model name |
| `method` | string | `"getListCount"` | Count method name |
| `params` | string | `"{}"` | JSON-encoded parameter dict |

**Response:**

```json
{"ok": true, "count": 483}
```

---

### `blesta_get_report`

Fetch a Blesta report for a specific date range.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `report_type` | string | required | Report type (e.g. `"package_revenue"`) |
| `start_date` | string | required | Start date as `"YYYY-MM-DD"` |
| `end_date` | string | required | End date as `"YYYY-MM-DD"` |
| `extra_vars` | string | `"{}"` | Additional `vars[]` parameters as JSON |

**Response (CSV report):**

```json
{"ok": true, "data": [{"Package": "Basic", "Revenue": "49.99"}, ...]}
```

---

### `blesta_get_report_series`

Fetch monthly reports across a date range as a flat list of rows.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `report_type` | string | required | Report type |
| `start_month` | string | required | Start month as `"YYYY-MM"` |
| `end_month` | string | required | End month as `"YYYY-MM"` |
| `extra_vars` | string | `"{}"` | Additional `vars[]` parameters as JSON |

Each row includes a `_period` key with the month in `"YYYY-MM"` format.

**Response:**

```json
{
  "ok": true,
  "count": 36,
  "data": [{"_period": "2024-01", "Package": "Basic", "Revenue": "49.99"}, ...]
}
```

---

### `blesta_list_models`

List all available Blesta API models from the bundled schema.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `source` | string | `null` | Filter by `"core"` or `"plugin"`; `null` for all |

**Response:**

```json
{"ok": true, "models": ["Clients", "Contacts", "Invoices", ...]}
```

---

### `blesta_list_methods`

List all method names for a specific model.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `model` | string | Model name (e.g. `"Clients"`) |

**Response:**

```json
{"ok": true, "model": "Clients", "methods": ["create", "delete", "edit", "get", "getList", ...]}
```

---

### `blesta_get_method_spec`

Return the full specification for a model/method pair.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `model` | string | Model name |
| `method` | string | Method name |

**Response:**

```json
{
  "ok": true,
  "model": "Clients",
  "method": "getList",
  "http_method": "GET",
  "description": "Returns a list of clients",
  "params": [{"name": "status", "type": "string", "required": false}, ...],
  "return_type": "array",
  "source": "core"
}
```

---

### `blesta_capabilities_report`

Generate a full capabilities report of the Blesta API surface.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `output_format` | string | `"markdown"` | `"markdown"` or `"json"` |

**Response (markdown):** A Markdown string listing all models and methods.

**Response (json):** A JSON array of model capability objects.

---

## Resources

Resources expose read-only data about the API schema without requiring live API credentials.

| URI | Description |
|-----|-------------|
| `blesta://schema/core` | Raw core API schema JSON (63 models) |
| `blesta://schema/plugin` | Raw plugin schema JSON (8 models) |
| `blesta://models` | JSON array of all model names |
| `blesta://models/{model}` | JSON object with model name and method list |
| `blesta://models/{model}/methods/{method}` | Full method spec JSON |
| `blesta://capabilities/markdown` | Full API capabilities as Markdown |
| `blesta://capabilities/json` | Full API capabilities as JSON |

---

## Prompts

Pre-built prompt templates for common Blesta AI workflows:

| Prompt | Description |
|--------|-------------|
| `blesta_audit_client` | Audit a client's account status, invoices, and services |
| `blesta_plan_migration` | Plan a data migration from one Blesta instance to another |
| `blesta_reconcile_invoices` | Reconcile invoices against payment transaction records |
| `blesta_extract_customer_snapshot` | Extract a complete customer data snapshot |
| `blesta_map_to_prime_account` | Map Blesta fields to a target billing system schema |

---

## Important Constraints

### Credentials at call time

Credentials are read from environment variables when each tool is invoked, not at server
startup. This means:

- The server can be started without credentials configured (tools will fail until env vars are set)
- Changing env vars between calls takes effect immediately
- Different MCP client sessions can use the same server process (credentials are per-env, not per-session)

### Transport layer only

The MCP server is a thin adapter over `blesta_sdk.core`. It does not provide:

- **Idempotency** for billing writes — duplicate tool calls can create duplicate records
- **Transaction semantics** — if a workflow fails mid-way, no rollback occurs
- **Rate limiting** — the underlying SDK retries 429s, but the MCP layer does not throttle

For billing mutations, always verify the method spec first with `blesta_get_method_spec`,
confirm the action with the user, and implement a ledger pattern for migrations.

### Read-heavy use case

The MCP server is designed for read-heavy workflows: auditing, reporting, schema
introspection, data extraction, and migration planning. For bulk creates or updates,
use the Python SDK directly with a ledger and check-then-create pattern.

---

## Programmatic Usage

To use the MCP package directly in Python (e.g. for testing or embedding):

```python
from blesta_sdk.mcp.tools import _call_handler, _get_all_handler
from blesta_sdk.mcp.resources import _models_handler, _model_handler

# All handlers return JSON strings
import json

result = json.loads(_call_handler("Clients", "getList", '{"status": "active"}'))
if result["ok"]:
    clients = result["data"]

models = json.loads(_models_handler())
```

See the [`blesta_sdk.mcp`](src/blesta_sdk/mcp/) source for all available handlers.
