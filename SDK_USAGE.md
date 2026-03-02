# SDK Usage Reference

Patterns and examples for writing code that uses `blesta_sdk`. This is a companion to `CLAUDE.md` (project conventions).

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
    max_retries=3,          # exponential backoff with jitter on 5xx/network errors
    retry_mutations=False,  # True to also retry POST/PUT (default: only GET/DELETE)
    pool_connections=10,    # connection pools to cache (default 10)
    pool_maxsize=10,        # max connections per pool (default 10)
)
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

No exceptions are raised for HTTP errors. Check the response:

```python
if response.status_code != 200:
    print(f"HTTP {response.status_code}: {response.errors()}")

if response.status_code == 0:
    print("Network error:", response.raw)
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
print(disco.generate_capabilities_report(format="markdown"))
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
    max_concurrency=10,             # shared semaphore for concurrent requests
    retry_mutations=False,          # same as sync client
)
```

Timeout is set at client init (httpx behavior) rather than per-request.

### Async Last Request (Concurrency-Safe)

In concurrent contexts, `get_last_request()` returns the last request from the current asyncio task (via `ContextVar`), not the last request globally on the instance:

```python
# Safe in concurrent tasks — each task sees its own last request
last = api.get_last_request()
```

## Debugging

```python
# Inspect the last request URL and parameters
response = api.get("clients", "getList", {"status": "active"})
last = api.get_last_request()
print(last["url"])   # "https://example.com/api/clients/getList.json"
print(last["args"])  # {"status": "active"}
```
