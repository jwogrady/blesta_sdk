# Blesta Python SDK

Python SDK and CLI for the [Blesta](https://www.blesta.com/) billing platform REST API.

This SDK is a **transport and helper layer** — it wraps authenticated HTTP access to Blesta
models and methods, handles response parsing, pagination, retries, error detection, schema
discovery, and environment configuration. It is not a full billing application, not a hosted
service, and does not provide idempotency guarantees by itself.

**What it does:**
- Wraps Blesta REST API calls with Basic Auth or header-based authentication
- Parses JSON and CSV responses; surfaces body-level Blesta errors (HTTP 200 can still mean failure)
- Provides automatic pagination, batch extraction, and report helpers
- Supports automatic retry with exponential backoff and jitter
- Includes bundled API schema discovery (63 core models, 8 plugin models)
- Provides environment-keyed credential management (`dev` / `stage` / `live`)
- Redacts sensitive fields from debug/log output via `get_last_request()`
- Ships both sync (`BlestaRequest`) and async (`AsyncBlestaRequest`) clients

**What it does not do:**
- Provide idempotency or deduplication for billing writes — that is the caller's responsibility
- Guarantee that a failed POST means no record was created (server errors can occur after a write)
- Operate as a hosted service, migration engine, or workflow orchestrator

## Installation

Requires Python 3.9+.

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv add blesta_sdk
```

Using pip:

```bash
pip install blesta_sdk
```

For CLI `.env` file support:

```bash
pip install blesta_sdk[cli]
```

For async support:

```bash
pip install blesta_sdk[async]
```

For the MCP server (Python 3.10+):

```bash
pip install blesta_sdk[mcp]
```

## Quickstart

### Sync

```python
from blesta_sdk import BlestaRequest

api = BlestaRequest(
    "https://billing.example.com/api",
    "api_user",
    "api_key",
    auth_method="header",
    raise_on_error=True,
)

response = api.get("clients", "getList", {"page": 1})
clients = response.data
```

### Async

```python
import asyncio
from blesta_sdk import AsyncBlestaRequest

async def main():
    async with AsyncBlestaRequest(
        "https://billing.example.com/api",
        "api_user",
        "api_key",
        max_concurrency=5,
        auth_method="header",
    ) as api:
        clients = await api.get_all("clients", "getList")

asyncio.run(main())
```

## Use Cases

### Good fits

| Use case | Notes |
|---|---|
| Admin scripts and cron jobs | Sync client; straightforward, restartable |
| Client/invoice/service extraction | Pagination helpers handle large datasets |
| Billing data audits and reconciliation | Read-only; no mutation risk |
| Migration planning and dry runs | Use async for parallel read extraction |
| Controlled Blesta-to-Blesta migrations | Pair with a ledger + check-then-create pattern |
| Reporting (monthly revenue, tax liability) | `get_report()` / `get_report_series()` handle CSV |
| Schema and capability inspection | `BlestaDiscovery` introspects all 71 models |
| Read-heavy concurrent extraction | Async `get_all_fast()` / `extract()` |
| Internal tooling around Blesta | CLI or programmatic API |

### Use with caution

| Use case | Risk |
|---|---|
| Bulk invoice / payment creation | Faster duplicates are worse than slower success; use a migration ledger |
| Retrying billing mutations without a ledger | `retry_mutations=True` never retries 5xx, but caller-side retry without dedup creates duplicates |
| HTTP in non-local environments | Credentials sent in plaintext; only use `allow_http=True` for local/dev |
| Treating HTTP 200 as success | Blesta returns HTTP 200 with `errors` on validation failures — always check `response.errors()` |
| Async concurrency for billing writes | Concurrent creates without dedup produce race conditions |

## Python API

### HTTP Methods

```python
from blesta_sdk import BlestaRequest

api = BlestaRequest("https://your-blesta-domain.com/api", "user", "key")

# GET — parameters sent as query string
response = api.get("clients", "getList", {"status": "active"})

# POST — parameters sent as JSON body
response = api.post("clients", "create", {"firstname": "John", "lastname": "Doe"})

# PUT
response = api.put("clients", "edit", {"client_id": 1, "firstname": "Jane"})

# DELETE
response = api.delete("clients", "delete", {"client_id": 1})
```

### Schema-Aware Calls

Use `call()` to let the SDK infer the correct HTTP method from the bundled API schema. If a method is not in the schema, the SDK infers the verb from the method name (e.g. `get*` -> GET, `create*` -> POST):

```python
# Automatically uses GET (inferred from schema)
response = api.call("clients", "getList", {"status": "active"})

# Automatically uses POST (inferred from schema)
response = api.call("clients", "create", {"firstname": "John"})

# Override with explicit action
response = api.call("clients", "create", {"firstname": "John"}, action="POST")
```

### Response Handling

```python
response = api.get("clients", "getList")

response.status_code   # HTTP status code (int); 0 on network errors
response.data          # parsed "response" field from JSON body
response.raw           # raw response body text
response.errors()      # error dict if present, otherwise None
response.is_json       # True if response is valid JSON
response.is_csv        # True if response is CSV data
response.csv_data      # parsed CSV rows as list of dicts, or None
```

> **Important:** Blesta can return HTTP 200 with an `errors` key for validation failures
> (e.g., duplicate client, missing required field). A `status_code` of 200 does **not**
> guarantee success. Always check `response.errors()` or use `raise_on_error=True`.

### Pagination

Prefer `iter_all()` for large datasets — it streams records without materializing all pages into
memory. Use `get_all()` only when you need the full list at once.

```python
# Memory-efficient generator (recommended for large datasets)
for client in api.iter_all("clients", "getList", {"status": "active"}):
    print(client["id"])

# Page-level iterator (useful for batch DB writes)
for page in api.iter_pages("clients", "getList"):
    db.bulk_insert(page)

# Collect all pages into a list
# WARNING: materializes all records into memory
all_clients = api.get_all("clients", "getList", {"status": "active"})

# Schema-aware variant (equivalent to get_all)
all_clients = api.call_all("clients", "getList")
```

Stuck-page protection prevents infinite loops: pagination aborts after 3 consecutive identical
pages and logs a warning.

#### Pagination Safety

```python
from blesta_sdk import PaginationError

try:
    for client in api.iter_all("clients", "getList", on_error="raise"):
        process(client)
except PaginationError as e:
    print(f"Failed on page {e.page}: HTTP {e.status_code}")
    print(f"Recovered {len(e.partial_items)} items before failure")
```

### Record Counts

```python
# Uses model/getListCount by default
total = api.count("clients")

# Custom count method
active = api.count("clients", "getStatusCount", {"status": "active"})

# Schema-aware: auto-discovers the count method for a list method
total = api.count_for("clients", "getList")
```

Returns `0` on errors or non-numeric responses.

### Batch Extraction

Pull multiple models in a single call for ETL workflows:

```python
data = api.extract([
    ("clients", "getList", {"status": "active"}),
    ("invoices", "getList"),
    ("packages", "getAll"),
])

for client in data["clients.getList"]:
    print(client["id"])
```

### Reports

Blesta reports return CSV data. The SDK handles the `vars[]` parameter format automatically.

```python
response = api.get_report("package_revenue", "2025-01-01", "2025-01-31")

for row in response.csv_data:
    print(row["Package"], row["Revenue"])
```

### Time-Series Reports

Fetch a report for each month in a date range:

```python
# Flat list with _period metadata
rows = api.get_report_series("package_revenue", "2024-01", "2024-12")
for row in rows:
    print(row["_period"], row["Package"], row["Revenue"])

# Generator variant — yields (period, response) tuples
for period, response in api.get_report_series_pages("tax_liability", "2024-01", "2024-12"):
    if response.status_code == 200:
        print(f"{period}: {len(response.csv_data)} rows")
```

### DataFrame Conversion

Requires pandas (`pip install pandas` or `uv add pandas`).

```python
response = api.get_report("package_revenue", "2025-01-01", "2025-01-31")
df = response.to_dataframe()

# Also works with JSON responses
response = api.get("clients", "getList", {"status": "active"})
df = response.to_dataframe()
```

### Connection Pool Tuning

For high-throughput workloads (pagination, batch extraction), tune the connection pool:

```python
api = BlestaRequest(url, user, key, pool_connections=20, pool_maxsize=20)
```

Defaults are `10`/`10`.

### Authentication

```python
# Default: HTTP Basic Auth
api = BlestaRequest(url, user, key)

# Header-based auth (recommended by Blesta for CGI/PHP-FPM setups)
api = BlestaRequest(url, user, key, auth_method="header")
```

#### HTTP URLs (local / dev only)

By default, `http://` base URLs raise `ValueError` to prevent credentials from being sent in
plaintext. Use `allow_http=True` as an explicit opt-in for local development or test environments:

```python
api = BlestaRequest(
    "http://localhost/blesta/api",
    "api_user",
    "api_key",
    allow_http=True,
)
```

> **Never use `allow_http=True` in production.** HTTP sends the API key and user in plaintext
> on every request.

### Context Manager

```python
with BlestaRequest("https://your-blesta-domain.com/api", "user", "key") as api:
    response = api.get("clients", "getList")
# session is closed automatically
```

## Error Handling

By default, all request methods return a `BlestaResponse` — no exceptions are raised for HTTP
errors or Blesta body errors:

```python
response = api.get("clients", "get", {"client_id": 999})

# Check HTTP status first
if response.status_code != 200:
    print(f"HTTP {response.status_code}: {response.errors()}")

# Always check for body-level errors even on HTTP 200
if response.errors():
    print(f"Blesta returned errors: {response.errors()}")
```

Network failures return `status_code=0`, distinguishable from any real HTTP status code:

```python
response = api.get("clients", "getList")
if response.status_code == 0:
    print("Network error:", response.raw)
```

> Blesta returns HTTP 200 with an `errors` key for validation failures. A `200` response
> does not mean success. Use `raise_on_error=True` or check `response.errors()` explicitly.

### Fail-Fast Mode

For scripts that want exception-based error handling, use `raise_on_error=True`. This raises
on HTTP errors **and** on HTTP 200 responses that contain Blesta body errors:

```python
from blesta_sdk import BlestaRequest, BlestaAPIError

api = BlestaRequest(url, user, key, raise_on_error=True)

try:
    response = api.post("clients", "create", payload)
except BlestaAPIError as exc:
    print(exc.errors)
```

Or call `raise_for_status()` manually on any response:

```python
response = api.post("clients", "create", payload)
response.raise_for_status()  # raises on 4xx/5xx/connection errors AND HTTP 200 body errors
```

Exception hierarchy:

| Exception | Trigger |
|---|---|
| `BlestaError` | Base class for all SDK exceptions |
| `BlestaConnectionError` | `status_code == 0` (network failure) |
| `BlestaAPIError` | 400–499 client errors, or HTTP 200 with body errors |
| `BlestaAuthError` | 401 / 403 specifically |
| `BlestaRateLimitError` | 429 (includes `.retry_after` seconds) |
| `BlestaServerError` | 500–599 server errors |

All exceptions carry `status_code`, `errors`, and `headers` attributes.

### Retry

For production pipelines, enable automatic retry with exponential backoff:

```python
api = BlestaRequest(url, user, key, max_retries=3)

# GET/DELETE: retry on network errors, 5xx, and 429 (with jitter)
# Does NOT retry on other 4xx client errors
response = api.get("clients", "getList")

# POST/PUT: retry ONLY on 429 (rate-limit), never on 5xx
# A 5xx does not guarantee the write failed — retrying risks duplicate billing records
response = api.post("clients", "create", {"firstname": "John"})
```

By default, only GET and DELETE are retried (`retry_mutations=False`). Pass
`retry_mutations=True` to include POST/PUT in the retry loop, but note that even
then **POST/PUT will never retry on 5xx — only on 429**. To safely handle server
errors on billing writes, use an idempotency pattern (ledger dedup or
check-before-create) rather than relying on automatic retry.

```python
# retry_mutations=True: POST/PUT will retry on 429 but NOT on 5xx
api = BlestaRequest(url, user, key, max_retries=3, retry_mutations=True)
```

### Rate Limiting

429 responses are automatically retried when `max_retries > 0`:

- If the server sends a `Retry-After` header, the client sleeps for that many seconds (integer format only; HTTP-date is not supported)
- If the header is absent or unparseable, falls back to exponential backoff with jitter
- `max_retries=0` (default) disables all retry, including 429

The `Retry-After` value is also available on exceptions:

```python
from blesta_sdk import BlestaRateLimitError

try:
    response.raise_for_status()
except BlestaRateLimitError as e:
    print(f"Retry after {e.retry_after} seconds")
```

## API Discovery

The SDK bundles machine-readable schemas for all 63 core Blesta models and 8 plugin models. Use `BlestaDiscovery` to introspect the available API surface:

```python
from blesta_sdk import BlestaDiscovery

disco = BlestaDiscovery()

# List all models
disco.list_models()                      # all models
disco.list_models(source="core")         # core models only
disco.list_models(source="plugin")       # plugin models only

# List methods for a model
disco.list_methods("Clients")            # ["create", "delete", "edit", ...]

# Get full method specification
spec = disco.get_method_spec("Clients", "getList")
spec.http_method   # "GET"
spec.params        # [{"name": "status", "type": "string", ...}]
spec.return_type   # "array"

# Resolve HTTP method for a call
disco.resolve_http_method("Clients", "getList")       # "GET"
disco.resolve_http_method("Clients", "create")         # "POST"

# Find pagination pairs
disco.suggest_pagination_pair("Clients", "getList")    # "getListCount"

# Generate a capabilities report
print(disco.generate_capabilities_report(output_format="markdown"))

# Generate JSONL index for AI embeddings
disco.generate_ai_index("blesta_api_index.jsonl")
```

## Async Client

Install with `pip install blesta_sdk[async]` (requires `httpx`).

`AsyncBlestaRequest` mirrors the full sync API with `async`/`await`:

```python
from blesta_sdk import AsyncBlestaRequest

async with AsyncBlestaRequest(url, user, key) as api:
    # All sync methods available as async
    response = await api.get("clients", "getList")
    all_clients = await api.get_all("clients", "getList")
    total = await api.count("clients")

    # Schema-aware helpers
    response = await api.call("clients", "getList")
    total = await api.count_for("clients")

    # Async generator for pagination
    async for client in api.iter_all("clients", "getList"):
        print(client["id"])

    # Concurrent batch extraction via asyncio.gather()
    data = await api.extract([
        ("clients", "getList"),
        ("invoices", "getList"),
    ])

    # Count-first parallel pagination
    all_clients = await api.get_all_fast("clients", "getList")

    # Concurrent monthly report fetching
    rows = await api.get_report_series_concurrent(
        "package_revenue", "2024-01", "2024-12", max_concurrency=5
    )
```

Constructor accepts `max_connections` and `max_keepalive_connections` (default `10`/`10`) instead of the sync `pool_connections`/`pool_maxsize`.

## Sync vs Async

### Use `BlestaRequest` (sync) for

- CLI tools and cron jobs
- Admin and maintenance scripts
- Controlled billing mutations where every write is logged or checkpointed
- Migrations with a ledger
- Simple reporting where concurrency is not needed
- Any context where simplicity and auditability matter more than throughput

### Use `AsyncBlestaRequest` for

- Read-heavy extraction across many models
- Concurrent report fetching (monthly/yearly report series)
- Count-first parallel pagination (`get_all_fast`)
- Async web applications or pipeline workers
- High-latency API reads where concurrency improves wall-clock time

### Avoid async for

- Uncontrolled billing writes — concurrent creates without dedup produce duplicate records
- Migrations without a ledger — faster doesn't help if records are duplicated
- Anything where a duplicate billing record is worse than a slow, sequential write

> For billing mutations in a migration, use the sync client with check-then-create and a
> migration ledger. Async is a tool for reading; sequential writes are safer for creating.

## Environment Configuration

`BlestaEnvConfig` selects credentials for a named deployment environment (dev, stage, or live) from environment variables or constructor keyword arguments.

### Environment Variables

| Environment | URL | User | Key |
|---|---|---|---|
| `dev` | `BLESTA_DEV_URL` | `BLESTA_DEV_USER` | `BLESTA_DEV_KEY` |
| `stage` | `BLESTA_STAGE_URL` | `BLESTA_STAGE_USER` | `BLESTA_STAGE_KEY` |
| `live` | `BLESTA_LIVE_URL` | `BLESTA_LIVE_USER` | `BLESTA_LIVE_KEY` |

`.env` file support requires the `cli` extra (`pip install blesta_sdk[cli]`).

### Key Behaviors

- Credentials for each environment are **fully isolated** — missing vars for `stage` will never fall back to `live`.
- Raises `ValueError` immediately if any of the three required vars are absent.
- `client()` returns a fully configured `BlestaRequest`. Any keyword arguments are forwarded to the constructor (e.g. `auth_method="header"`, `raise_on_error=True`).

### Usage

```python
from blesta_sdk import BlestaEnvConfig

cfg = BlestaEnvConfig("stage")
api = cfg.client(auth_method="header", raise_on_error=True)
response = api.get("clients", "getList")
```

Credentials can also be passed directly as keyword arguments:

```python
cfg = BlestaEnvConfig("dev", url="https://dev.example.com/api", user="u", key="k")
api = cfg.client(max_retries=3)
```

See `.env.example` for a template covering all three environments.

## Debugging and Redaction

`get_last_request()` returns the URL and args of the most recent request, with sensitive
fields automatically redacted. It is safe to log or print — the actual request payload is
never modified:

```python
response = api.get("clients", "getList", {"status": "active"})
last = api.get_last_request()
print(last["url"])   # "https://example.com/api/clients/getList.json"
print(last["args"])  # {"status": "active"}  — sensitive keys replaced with "***"
```

Redacted field examples:

- Exact matches: `password`, `token`, `api_key`, `secret`, `card_number`, `cvv`, `ssn`, `pin`
- Suffix matches: any field ending in `_key`, `_secret`, `_password`, or `_token`
- Nested dicts and lists are redacted recursively

> Redaction applies only to the debug copy returned by `get_last_request()`. The actual
> HTTP request is sent with the original values intact.

In async contexts, `get_last_request()` is per-task (via `ContextVar`), so concurrent
tasks each see their own last request.

## Migration Safety

The SDK is a transport and helper layer — it does not provide idempotency or deduplication
for billing writes. For Blesta-to-Blesta or external-to-Blesta migrations, use the following
pattern:

1. **Migration ledger** — maintain an external mapping of source IDs to target IDs
2. **Check-then-create** — query the target before writing; skip if the record already exists
3. **Source IDs in custom fields** — embed `source_id` so records are recoverable if the ledger is lost
4. **Sequential writes** — use the sync client for creates; do not parallelize billing mutations

Key rules:
- Do **not** rely on `retry_mutations=True` as an idempotency mechanism. A 5xx response after a POST does not mean the write failed — Blesta may have already committed it.
- Do **not** assume a failed POST means no record was created.
- Do **not** run bulk creates in parallel without a distributed lock.

See [`docs/migration.md`](docs/migration.md) for full patterns with code examples.

## CLI

The `blesta` command reads credentials from environment variables. With the `cli` extra installed (`pip install blesta_sdk[cli]`), it also loads a `.env` file in the current directory:

```env
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

Generate API credentials in Blesta under Settings > System > API Access.

### Subcommands

```
blesta call   <model> <method> [--action GET|POST|PUT|DELETE] [--param key=value ...]
blesta extract <model> <method> [--param key=value ...] [--format json|jsonl|csv]
blesta report  <type> --start YYYY-MM-DD --end YYYY-MM-DD [--param key=value ...]
blesta discover models|methods <model>|spec <model> <method>
```

### Legacy mode (still supported)

```
blesta --model <model> --method <method> [--action GET|POST|PUT|DELETE] [--params key=value ...]
```

### Examples

```bash
# List active clients (subcommand form)
blesta call clients getList --param status=active

# Paginate all clients into a JSONL stream
blesta extract clients getList --format jsonl

# Fetch a revenue report
blesta report package_revenue --start 2025-01-01 --end 2025-03-31

# Discover available models
blesta discover models

# List methods for a model
blesta discover methods clients

# Show full method spec
blesta discover spec clients getList
```

Output is JSON to stdout. On errors, the error dict is printed as JSON and the process exits with code 1.

See [`CLI_USAGE.md`](CLI_USAGE.md) for the full CLI reference.

## MCP Server

The `blesta-mcp` command exposes the full Blesta API as an [MCP](https://modelcontextprotocol.io/) server for use with Claude, Cursor, and other MCP-compatible AI tools.

Requires Python 3.10+ and the `mcp` extra:

```bash
pip install blesta_sdk[mcp]
```

Configure credentials via environment variables (same as the CLI), then run:

```bash
blesta-mcp
```

Or register it in your MCP client configuration (e.g. Claude Desktop / Claude Code):

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

### Tools

| Tool | Description |
|---|---|
| `blesta_call` | Invoke any single API method |
| `blesta_get_all` | Paginate a list endpoint and return all records |
| `blesta_extract` | Fetch multiple paginated endpoints at once |
| `blesta_count` | Fetch a record count |
| `blesta_get_report` | Fetch a Blesta report (CSV or JSON) |
| `blesta_get_report_series` | Fetch monthly reports across a date range |
| `blesta_list_models` | List all available API models |
| `blesta_list_methods` | List methods for a model |
| `blesta_get_method_spec` | Get full spec for a model/method pair |
| `blesta_capabilities_report` | Generate a full API capabilities report |

### Resources

| Resource URI | Description |
|---|---|
| `blesta://schema/core` | Raw core API schema JSON |
| `blesta://schema/plugin` | Raw plugin schema JSON |
| `blesta://models` | All available model names |
| `blesta://models/{model}` | Methods for a specific model |
| `blesta://models/{model}/methods/{method}` | Full spec for a model/method |
| `blesta://capabilities/markdown` | API capabilities report (Markdown) |
| `blesta://capabilities/json` | API capabilities report (JSON) |

See [`MCP_USAGE.md`](MCP_USAGE.md) for the full MCP server reference.

## API Reference

### `BlestaRequest(url, user, key, timeout=30, max_retries=0, retry_mutations=False, pool_connections=10, pool_maxsize=10, auth_method="basic", raise_on_error=False, allow_http=False, discovery=None)`

| Method | Description |
|---|---|
| `get(model, method, args=None)` | GET request (query parameters) |
| `post(model, method, args=None)` | POST request (JSON body) |
| `put(model, method, args=None)` | PUT request (JSON body) |
| `delete(model, method, args=None)` | DELETE request (JSON body) |
| `submit(model, method, args=None, action="POST")` | Send request with explicit HTTP method |
| `call(model, method, args=None, action=None)` | Schema-aware request (infers HTTP method from schema, then method name) |
| `count(model, method="getListCount", args=None)` | Fetch record count as `int` (`0` on error) |
| `count_for(model, list_method="getList", args=None)` | Schema-aware count (auto-discovers count method) |
| `iter_all(model, method, args=None, start_page=1, max_pages=None, on_error="warn")` | Paginate and yield individual results |
| `iter_pages(model, method, args=None, start_page=1, max_pages=None, on_error="warn")` | Paginate and yield each page as a list |
| `get_all(model, method, args=None, start_page=1, max_pages=None)` | Paginate and return all results as a list |
| `call_all(model, method, args=None, start_page=1)` | Schema-aware pagination (equivalent to `get_all`) |
| `extract(targets)` | Batch-fetch multiple paginated endpoints |
| `get_report(report_type, start_date, end_date, extra_vars=None)` | Fetch a Blesta report (CSV) |
| `get_report_series(report_type, start_month, end_month, extra_vars=None)` | Monthly reports as flat row list |
| `get_report_series_pages(report_type, start_month, end_month, extra_vars=None)` | Monthly reports as generator |
| `get_last_request()` | Last request URL and args (sensitive fields redacted), or `None` |
| `close()` | Close the HTTP session |

Supports context manager (`with BlestaRequest(...) as api:`).

### `AsyncBlestaRequest(url, user, key, timeout=30, max_retries=0, retry_mutations=False, max_connections=10, max_keepalive_connections=10, max_concurrency=10, auth_method="basic", raise_on_error=False, allow_http=False, discovery=None)`

Same methods as `BlestaRequest`, all `async`. Additional async-specific methods:

| Method | Description |
|---|---|
| `get_all_fast(model, method, count_method="getListCount", args=None, page_size=25, batch_size=10)` | Count-first parallel pagination |
| `get_report_series_concurrent(report_type, start_month, end_month, extra_vars=None, max_concurrency=None)` | Concurrent monthly report fetching |

`extract()` runs targets concurrently via `asyncio.gather()`. `iter_all()` is an async generator (`async for`). Supports `async with` context manager.

In concurrent contexts, `get_last_request()` returns the last request for the current asyncio task only.

### `BlestaEnvConfig(env, *, url=None, user=None, key=None)`

Resolves Blesta credentials for a named deployment environment.

| Parameter | Description |
|---|---|
| `env` | One of `"dev"`, `"stage"`, or `"live"` |
| `url` | API base URL — falls back to `BLESTA_{ENV}_URL` env var |
| `user` | API user — falls back to `BLESTA_{ENV}_USER` env var |
| `key` | API key — falls back to `BLESTA_{ENV}_KEY` env var |

Raises `ValueError` if `env` is not recognized, or if any credential cannot be resolved.

| Method / Property | Description |
|---|---|
| `client(**kwargs)` | Return a `BlestaRequest` for this environment. Extra kwargs forwarded to constructor. |
| `env` | The environment name |
| `url` | Resolved API base URL |
| `user` | Resolved API user |

### `BlestaDiscovery(core_schema_path=None, plugin_schema_path=None)`

| Method | Description |
|---|---|
| `list_models(source=None)` | List all model names (filterable by `"core"` or `"plugin"`) |
| `list_methods(model)` | List method names for a model |
| `get_method_spec(model, method)` | Get full `MethodSpec` dataclass for a method |
| `resolve_http_method(model, method, default="POST")` | Resolve HTTP method from schema |
| `suggest_pagination_pair(model, list_method="getList")` | Find the count method for a list method |
| `generate_capabilities_report(output_format="markdown")` | Generate API capabilities report (`"markdown"` or `"json"`) |
| `generate_ai_index(path)` | Write JSONL index for AI embeddings |

### `BlestaResponse`

| Property / Method | Type | Description |
|---|---|---|
| `status_code` | `int` | HTTP status code; `0` = network error |
| `data` | `Any \| None` | Parsed `"response"` field from JSON body |
| `raw` | `str \| None` | Raw response body text |
| `headers` | `Mapping[str, str]` | HTTP response headers |
| `errors()` | `dict \| None` | Error dict if present (including HTTP 200 body errors), otherwise `None` |
| `is_json` | `bool` | `True` if response is valid JSON |
| `is_csv` | `bool` | `True` if response is CSV data |
| `csv_data` | `list[dict] \| None` | Parsed CSV rows, or `None` |
| `to_dataframe()` | `DataFrame` | Convert to pandas DataFrame (requires pandas) |
| `raise_for_status()` | `None` | Raise typed exception on error or HTTP 200 body errors; no-op for clean 1xx–3xx |
| `free_raw()` | `None` | Release raw text to save memory (caches preserved) |

### Exceptions

| Exception | Trigger |
|---|---|
| `BlestaError` | Base class |
| `BlestaConnectionError` | `status_code == 0` |
| `BlestaAPIError` | 400–499, or HTTP 200 with body errors |
| `BlestaAuthError` | 401 / 403 |
| `BlestaRateLimitError` | 429 (`.retry_after` attribute) |
| `BlestaServerError` | 500–599 |
| `PaginationError` | Pagination failure with `on_error="raise"` (`.page`, `.status_code`, `.partial_items`) |

### `__version__`

The installed package version is available at runtime:

```python
import blesta_sdk
print(blesta_sdk.__version__)  # e.g. "0.6.0"
```

## Blesta API Reference

- [API Guide](https://docs.blesta.com/developers/api) — authentication, URL structure, error codes
- [API Models](https://source-docs.blesta.com/packages/blesta-app-models.html) — all available API models
- [API Controllers](https://source-docs.blesta.com/packages/blesta-app-controllers.html) — admin, client, and system controllers

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Run tests: `uv run pytest -v -m "not integration"`
4. Run linting: `uv run ruff check src/ tests/ tools/`
5. Submit a pull request

## License

[MIT](https://github.com/jwogrady/blesta_sdk/blob/master/LICENSE)
