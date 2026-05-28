# SDK Usage Reference

Patterns and examples for writing code that uses `blesta_sdk`. This is a companion to `CLAUDE.md` (project conventions).

## Import Paths

The top-level `blesta_sdk` namespace re-exports everything. All public names are importable
from both the legacy flat path and the new canonical sub-packages:

```python
# Recommended: top-level imports (always stable)
from blesta_sdk import BlestaRequest, AsyncBlestaRequest
from blesta_sdk import BlestaEnvConfig
from blesta_sdk import BlestaDiscovery, MethodSpec
from blesta_sdk import BlestaError, BlestaAPIError, BlestaAuthError
from blesta_sdk import BlestaRateLimitError, BlestaServerError, PaginationError
from blesta_sdk import BlestaResponse

# Canonical sub-package imports (v0.8+)
from blesta_sdk.core import BlestaRequest, BlestaEnvConfig
from blesta_sdk.discovery import BlestaDiscovery, MethodSpec
```

The `blesta_sdk.mcp` namespace is separate and requires `pip install blesta_sdk[mcp]`:

```python
from blesta_sdk.mcp.tools import _call_handler   # tool handlers
from blesta_sdk.mcp.resources import _models_handler  # resource handlers
```

## Initialization

All API calls go through `model`/`method` pairs that map to Blesta's REST routes (`/api/model/method.json`). For plugin models, use dot notation: `"plugin.model"`.

```python
from blesta_sdk import BlestaRequest

api = BlestaRequest(
    url="https://example.com/api",
    user="api_user",
    key="api_key",
    auth_method="header",   # or "basic" (default)
    timeout=30,             # seconds, default 30
    max_retries=3,          # GET/DELETE: retry on 5xx/network errors/429; POST/PUT: 429 only
    retry_mutations=False,  # True to include POST/PUT in retry loop (429 only, never 5xx)
    pool_connections=10,    # connection pools to cache (default 10)
    pool_maxsize=10,        # max connections per pool (default 10)
    raise_on_error=False,   # True to raise BlestaError on HTTP errors AND HTTP 200 body errors
    allow_http=False,       # True to permit http:// URLs (local/dev only — sends key in plaintext)
)
```

Use `allow_http=True` only for local development — HTTP sends credentials in plaintext:

```python
# Local dev only
api = BlestaRequest("http://localhost/blesta/api", "user", "key", allow_http=True)
```

Or as a context manager:

```python
with BlestaRequest(url, user, key) as api:
    response = api.get("clients", "getList")
# session closed automatically
```

## Requests and Responses

### Explicit HTTP Methods

```python
response = api.get("clients", "getList", {"page": 1})
response = api.post("clients", "create", {"firstname": "John", ...})
response = api.put("clients", "edit", {"client_id": 1, ...})
response = api.delete("clients", "delete", {"client_id": 1})

# Explicit action override via submit()
response = api.submit("clients", "create", {"firstname": "John"}, action="POST")
```

### Schema-Aware Calls

`call()` infers the HTTP method from the bundled API schema. If a method is not in the schema, the SDK infers the verb from the method name (e.g. `get*` -> GET, `create*` -> POST, `edit*` -> PUT, `delete*` -> DELETE). If still ambiguous, defaults to POST with a warning.

```python
response = api.call("clients", "getList")   # infers GET
response = api.call("clients", "create", {"firstname": "John"})  # infers POST

# Override the inferred method
response = api.call("clients", "create", {"firstname": "John"}, action="POST")
```

### BlestaResponse

Every method returns a `BlestaResponse` — even on network failure (`status_code=0`):

```python
response.status_code   # int: HTTP status code (0 on network error)
response.data          # parsed JSON "response" field, or None
response.raw           # raw response body as str
response.errors()      # dict of errors, or None on success
response.is_json       # bool
response.is_csv        # bool
response.csv_data      # list[dict] for CSV responses, or None (cached after first access)
response.to_dataframe()  # pandas DataFrame (requires pandas)
response.free_raw()      # release raw text to save memory (parsed data still works)
```

### Error Handling

No exceptions are raised for HTTP errors by default. Check the response:

```python
if response.status_code != 200:
    print(f"HTTP {response.status_code}: {response.errors()}")

if response.status_code == 0:
    print("Network error:", response.raw)
```

> **Important:** Blesta can return HTTP 200 with an `errors` key for validation failures
> (e.g., duplicate client, missing required field). A `status_code` of 200 does **not**
> guarantee the write succeeded. Always check `response.errors()`:

```python
response = api.post("clients", "create", payload)
if response.status_code == 200 and not response.errors():
    target_id = response.data["id"]
else:
    print("Create failed:", response.errors())
```

Use `raise_on_error=True` to raise automatically on HTTP errors **and** HTTP 200 body errors:

```python
from blesta_sdk import BlestaRequest, BlestaAPIError

api = BlestaRequest(url, user, key, raise_on_error=True)

try:
    response = api.post("clients", "create", payload)
    target_id = response.data["id"]
except BlestaAPIError as exc:
    print(exc.errors)
```

## Pagination

```python
# Iterator (memory-efficient, yields individual items)
for client in api.iter_all("clients", "getList"):
    print(client["id"])

# Page-level iterator (yields one list per page — useful for batch DB writes)
for page in api.iter_pages("clients", "getList"):
    db.bulk_insert(page)

# Collect all pages into a list
# WARNING: materializes all records into memory. For 100k+ records,
# prefer iter_all() or iter_pages() for streaming.
all_clients = api.get_all("clients", "getList")

# Schema-aware variant (equivalent to get_all)
all_clients = api.call_all("clients", "getList")

# Start from a specific page
page_5_onward = api.get_all("clients", "getList", start_page=5)

# Limit number of pages fetched
first_10_pages = api.get_all("clients", "getList", max_pages=10)
```

### Pagination Safety

```python
from blesta_sdk import PaginationError

# Raise on pagination errors (default silently stops)
try:
    for client in api.iter_all("clients", "getList", on_error="raise"):
        process(client)
except PaginationError as e:
    print(f"Failed on page {e.page}: HTTP {e.status_code}")
    print(f"Recovered {len(e.partial_items)} items before failure")
```

## Record Counts

```python
# Uses model/getListCount by default
total = api.count("clients")  # returns int, 0 on error

# Custom count method
active = api.count("clients", "getStatusCount", {"status": "active"})

# Schema-aware: auto-discovers the count method for a list method
total = api.count_for("clients", "getList")
```

## Batch Extraction

```python
data = api.extract([
    ("clients", "getList"),
    ("invoices", "getList"),
    ("transactions", "getList", {"status": "approved"}),
])
# data["clients.getList"] -> list of all clients
```

## Reports

```python
# Single report (returns CSV response)
response = api.get_report("tax_liability", "2025-01-01", "2025-12-31")
rows = response.csv_data  # list[dict[str, str]]

# Monthly time-series (adds "_period" key to each row)
rows = api.get_report_series("tax_liability", "2025-01", "2025-12")

# Generator: yields (period, response) tuples for each month
for period, response in api.get_report_series_pages("tax_liability", "2025-01", "2025-12"):
    if response.status_code == 200:
        print(f"{period}: {len(response.csv_data)} rows")
```

## DataFrame Conversion

Requires `pandas` (`pip install pandas`).

```python
# CSV response
response = api.get_report("package_revenue", "2025-01-01", "2025-01-31")
df = response.to_dataframe()

# JSON response (uses pandas.json_normalize)
response = api.get("clients", "getList", {"status": "active"})
df = response.to_dataframe()
```

## API Discovery

Introspect the bundled API schemas (63 core models, 8 plugin models):

```python
from blesta_sdk import BlestaDiscovery, MethodSpec

disco = BlestaDiscovery()

# List models
disco.list_models()                     # all models
disco.list_models(source="core")        # core only
disco.list_models(source="plugin")      # plugin only

# List methods for a model
disco.list_methods("Clients")           # ["create", "delete", "edit", ...]

# Get full method specification (returns frozen MethodSpec dataclass)
spec = disco.get_method_spec("Clients", "getList")
spec.http_method          # "GET"
spec.description          # "Fetches a list of all clients"
spec.params               # [{"name": "status", "type": "string", ...}]
spec.return_type          # "array"
spec.return_description   # "A list of stdClass objects ..."
spec.category             # "api" or "internal"
spec.source               # "core" or "plugin"
spec.signature            # PHP-style signature string

# Resolve HTTP method
disco.resolve_http_method("Clients", "getList")       # "GET"
disco.resolve_http_method("Clients", "create")         # "POST"
disco.resolve_http_method("Unknown", "unknown")        # "POST" (default)

# Find pagination pairs
disco.suggest_pagination_pair("Clients", "getList")    # "getListCount"

# Generate reports
print(disco.generate_capabilities_report(output_format="markdown"))
disco.generate_ai_index("blesta_api_index.jsonl")  # returns entry count
```

Custom schema paths (defaults to bundled schemas):

```python
disco = BlestaDiscovery(
    core_schema_path="path/to/core_schema.json",
    plugin_schema_path="path/to/plugin_schema.json",
)
```

## Async Client

Install with `pip install blesta_sdk[async]` (requires `httpx`).

`AsyncBlestaRequest` mirrors the full sync API with `async`/`await`:

```python
from blesta_sdk import AsyncBlestaRequest

async with AsyncBlestaRequest(url, user, key, auth_method="header") as api:
    # All sync methods available as async
    response = await api.get("clients", "getList")
    all_clients = await api.get_all("clients", "getList")
    total = await api.count("clients")

    # Schema-aware helpers
    response = await api.call("clients", "getList")
    all_clients = await api.call_all("clients", "getList")
    total = await api.count_for("clients", "getList")

    # Async pagination generator
    async for client in api.iter_all("clients", "getList"):
        print(client["id"])

    # Async page-level iterator
    async for page in api.iter_pages("clients", "getList"):
        await db.bulk_insert(page)

    # Concurrent batch extraction (via asyncio.gather)
    data = await api.extract([("clients", "getList"), ("invoices", "getList")])

    # Count-first parallel pagination (fetches pages in batches)
    # Set verify=True to re-count after fetching and warn on TOCTOU mismatch
    all_items = await api.get_all_fast("invoices", "getList", batch_size=5, verify=True)

    # Concurrent monthly reports
    rows = await api.get_report_series_concurrent(
        "tax_liability", "2025-01", "2025-12", max_concurrency=4
    )
```

### Async Constructor Differences

```python
AsyncBlestaRequest(
    url, user, key,
    max_connections=10,              # instead of pool_connections
    max_keepalive_connections=10,    # instead of pool_maxsize
    max_concurrency=10,              # shared semaphore for concurrent requests
    retry_mutations=False,           # same as sync client (POST/PUT: 429 only, never 5xx)
    allow_http=False,                # permit http:// URLs (local/dev only)
    discovery=None,                  # inject custom BlestaDiscovery instance
)
```

Timeout is set at client init (httpx behavior) rather than per-request.

### Async Last Request (Concurrency-Safe)

In concurrent contexts, `get_last_request()` returns the last request from the current asyncio task (via `ContextVar`), not the last request globally on the instance:

```python
# Safe in concurrent tasks — each task sees its own last request
last = api.get_last_request()
```

## Environment Configuration

`BlestaEnvConfig` selects credentials for a named deployment environment (`dev`, `stage`, or
`live`) from environment variables. No fallback between environments — missing `stage` vars
will never silently read `live` values.

```python
from blesta_sdk import BlestaEnvConfig

# Reads BLESTA_STAGE_URL, BLESTA_STAGE_USER, BLESTA_STAGE_KEY from env
cfg = BlestaEnvConfig("stage")
api = cfg.client(auth_method="header", raise_on_error=True)
response = api.get("clients", "getList")
```

Override credentials inline (useful in tests):

```python
cfg = BlestaEnvConfig("dev", url="https://dev.example.com/api", user="u", key="k")
api = cfg.client(max_retries=3)
```

`.env` file support requires `pip install blesta_sdk[cli]`. See `.env.example` for the
full variable template.

## Debugging and Redaction

`get_last_request()` returns the URL and args of the most recent request. Sensitive
fields are automatically redacted in the returned dict — the actual HTTP request is
not modified:

```python
# Inspect the last request URL and parameters
response = api.get("clients", "getList", {"status": "active"})
last = api.get_last_request()
print(last["url"])   # "https://example.com/api/clients/getList.json"
print(last["args"])  # {"status": "active"} — sensitive keys replaced with "***"
```

Redacted fields:
- Exact matches: `password`, `token`, `api_key`, `secret`, `card_number`, `cvv`, `ssn`, `pin`
- Suffix matches: any key ending in `_key`, `_secret`, `_password`, or `_token`
- Nested dicts and lists are redacted recursively

The redacted dict is safe to log or include in debug output. It will not expose API keys,
passwords, or payment data even when structured payloads contain nested credentials.

In async contexts, `get_last_request()` returns the last request for the **current asyncio
task** (via `ContextVar`). Concurrent tasks each see their own last request.
