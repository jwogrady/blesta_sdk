# Blesta Python SDK

Python SDK and CLI for the [Blesta](https://www.blesta.com/) billing platform REST API.

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

### `BlestaRequest(url, user, key, timeout=30)`

| Method | Description |
|---|---|
| `get(model, method, args=None)` | GET request (query parameters) |
| `post(model, method, args=None)` | POST request (JSON body) |
| `put(model, method, args=None)` | PUT request (JSON body) |
| `delete(model, method, args=None)` | DELETE request (JSON body) |
| `iter_all(model, method, args=None, start_page=1)` | Paginate and yield individual results |
| `get_all(model, method, args=None, start_page=1)` | Paginate and return all results as a list |
| `get_report(report_type, start_date, end_date, extra_vars=None)` | Fetch a Blesta report (CSV) |
| `get_report_series(report_type, start_month, end_month, extra_vars=None)` | Monthly reports as flat row list |
| `get_report_series_pages(report_type, start_month, end_month, extra_vars=None)` | Monthly reports as generator |
| `get_last_request()` | Last request URL and args, or `None` |
| `close()` | Close the HTTP session |

Supports context manager (`with BlestaRequest(...) as api:`).

### `BlestaResponse`

| Property / Method | Type | Description |
|---|---|---|
| `status_code` | `int` | HTTP status code; `0` = network error |
| `data` | `Any \| None` | Parsed `"response"` field from JSON body |
| `raw` | `str` | Raw response body text |
| `errors()` | `dict \| None` | Error dict if present, otherwise `None` |
| `is_json` | `bool` | `True` if response is valid JSON |
| `is_csv` | `bool` | `True` if response is CSV data |
| `csv_data` | `list[dict] \| None` | Parsed CSV rows, or `None` |
| `to_dataframe()` | `DataFrame` | Convert to pandas DataFrame (requires pandas) |

## Blesta API Reference

- [API Guide](https://docs.blesta.com/developers/api) — authentication, URL structure, error codes
- [API Models](https://source-docs.blesta.com/packages/blesta-app-models.html) — all available API models
- [API Controllers](https://source-docs.blesta.com/packages/blesta-app-controllers.html) — admin, client, and system controllers

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Run tests: `uv run pytest -v -m "not integration"`
4. Run linting: `uv run ruff check src/ tests/`
5. Submit a pull request

## License

[MIT](https://github.com/jwogrady/blesta_sdk/blob/master/LICENSE)
