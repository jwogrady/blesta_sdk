# Blesta Python SDK

Python SDK and CLI for the [Blesta](https://www.blesta.com/) billing platform REST API. Provides standardized, reliable methods to extract, query, and sync data from live Blesta instances — designed for developers building integrations, data pipelines, and AI-powered solutions.

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

## Quickstart

```python
from blesta_sdk import BlestaRequest

api = BlestaRequest("https://your-blesta-domain.com/api", "user", "key")

response = api.get("clients", "getList", {"status": "active"})
if response.status_code == 200:
    print(response.data)
else:
    print(response.errors())
```

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

### Pagination

```python
# Collect all pages into a list
all_clients = api.get_all("clients", "getList", {"status": "active"})

# Memory-efficient generator
for client in api.iter_all("clients", "getList", {"status": "active"}):
    print(client["id"])

# Schema-aware variant (equivalent to get_all)
all_clients = api.call_all("clients", "getList")
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

### Context Manager

```python
with BlestaRequest("https://your-blesta-domain.com/api", "user", "key") as api:
    response = api.get("clients", "getList")
# session is closed automatically
```

## Error Handling

All request methods return a `BlestaResponse`. No exceptions are raised for HTTP errors.

```python
response = api.get("clients", "get", {"client_id": 999})

if response.status_code != 200:
    print(f"HTTP {response.status_code}: {response.errors()}")
```

Network failures return `status_code=0`, distinguishable from any real HTTP status code:

```python
response = api.get("clients", "getList")
if response.status_code == 0:
    print("Network error:", response.raw)
```

### Retry

For production pipelines, enable automatic retry with exponential backoff:

```python
api = BlestaRequest(url, user, key, max_retries=3)

# Retries on network errors and 5xx responses (1s, 2s, 4s delays)
# Does NOT retry on 4xx client errors
response = api.get("clients", "getList")
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
print(disco.generate_capabilities_report(format="markdown"))

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

## CLI

The `blesta` command reads credentials from environment variables. With the `cli` extra installed (`pip install blesta_sdk[cli]`), it also loads a `.env` file in the current directory:

```env
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

Generate API credentials in Blesta under Settings > System > API Access.

### Usage

```
blesta --model <model> --method <method> [--action GET|POST|PUT|DELETE] [--params key=value ...] [--last-request]
```

### Examples

```bash
# List active clients
blesta --model clients --method getList --params status=active

# Get a specific client
blesta --model clients --method get --params client_id=1

# Create a client via POST
blesta --model clients --method create --action POST --params firstname=John lastname=Doe

# Show the URL and parameters of the request
blesta --model clients --method getList --last-request
```

Output is JSON to stdout. On errors, the error dict is printed as JSON and the process exits with code 1.

## API Reference

### `BlestaRequest(url, user, key, timeout=30, max_retries=0, retry_mutations=False, pool_connections=10, pool_maxsize=10, auth_method="basic")`

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
| `get_last_request()` | Last request URL and args, or `None` |
| `close()` | Close the HTTP session |

Supports context manager (`with BlestaRequest(...) as api:`).

### `AsyncBlestaRequest(url, user, key, timeout=30, max_retries=0, retry_mutations=False, max_connections=10, max_keepalive_connections=10, max_concurrency=10, auth_method="basic")`

Same methods as `BlestaRequest`, all `async`. Additional async-specific methods:

| Method | Description |
|---|---|
| `get_all_fast(model, method, count_method="getListCount", args=None, page_size=25, batch_size=10)` | Count-first parallel pagination |
| `get_report_series_concurrent(report_type, start_month, end_month, extra_vars=None, max_concurrency=None)` | Concurrent monthly report fetching |

`extract()` runs targets concurrently via `asyncio.gather()`. `iter_all()` is an async generator (`async for`). Supports `async with` context manager.

### `BlestaDiscovery(core_schema_path=None, plugin_schema_path=None)`

| Method | Description |
|---|---|
| `list_models(source=None)` | List all model names (filterable by `"core"` or `"plugin"`) |
| `list_methods(model)` | List method names for a model |
| `get_method_spec(model, method)` | Get full `MethodSpec` dataclass for a method |
| `resolve_http_method(model, method, default="POST")` | Resolve HTTP method from schema |
| `suggest_pagination_pair(model, list_method="getList")` | Find the count method for a list method |
| `generate_capabilities_report(format="markdown")` | Generate API capabilities report |
| `generate_ai_index(path)` | Write JSONL index for AI embeddings |

### `BlestaResponse`

| Property / Method | Type | Description |
|---|---|---|
| `status_code` | `int` | HTTP status code; `0` = network error |
| `data` | `Any \| None` | Parsed `"response"` field from JSON body |
| `raw` | `str \| None` | Raw response body text |
| `errors()` | `dict \| None` | Error dict if present, otherwise `None` |
| `is_json` | `bool` | `True` if response is valid JSON |
| `is_csv` | `bool` | `True` if response is CSV data |
| `csv_data` | `list[dict] \| None` | Parsed CSV rows, or `None` |
| `to_dataframe()` | `DataFrame` | Convert to pandas DataFrame (requires pandas) |

### `__version__`

The installed package version is available at runtime:

```python
import blesta_sdk
print(blesta_sdk.__version__)  # e.g. "0.5.0"
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
