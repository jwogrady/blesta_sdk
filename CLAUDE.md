# CLAUDE.md — Project Conventions for blesta_sdk

## Project Overview

Python SDK and CLI for the Blesta billing platform REST API. Wraps HTTP requests with Basic Auth or header-based authentication and provides structured response handling, automatic pagination, batch extraction, and optional async support.

## Tech Stack

- **Python** >= 3.9
- **Build**: hatchling (via `uv`)
- **Runtime deps**: `requests`
- **Optional deps**: `python-dotenv` (CLI `.env` support, `pip install blesta_sdk[cli]`), `httpx` (async client, `pip install blesta_sdk[async]`)
- **Dev tools**: pytest, pytest-cov, pytest-asyncio, pytest-benchmark, black, ruff

## Common Commands

```bash
uv sync                                    # Install all dependencies
uv run pytest -v                           # Run tests
uv run pytest -m "not integration"         # Skip live API integration tests
uv run pytest --cov=blesta_sdk --cov-report=term-missing --cov-fail-under=97  # Coverage check
uv run black src/ tests/                   # Format code
uv run ruff check src/ tests/              # Lint
uv build                                   # Build package
```

## Project Structure

- `src/blesta_sdk/__init__.py` — public API exports (`__all__`), lazy import for `AsyncBlestaRequest`
- `src/blesta_sdk/_client.py` — `BlestaRequest`: sync HTTP client (GET/POST/PUT/DELETE, pagination, reports, batch extraction)
- `src/blesta_sdk/_async_client.py` — `AsyncBlestaRequest`: async HTTP client (mirrors sync API, adds `get_all_fast()` and `get_report_series_concurrent()`)
- `src/blesta_sdk/_response.py` — `BlestaResponse`: response parsing, CSV/JSON detection, error extraction
- `src/blesta_sdk/_dateutil.py` — internal date range utilities for time-series reports
- `src/blesta_sdk/_cli.py` — CLI entry point (registered as `blesta` in pyproject.toml)
- `tests/` — unit tests (mocked) + one live integration test (`test_credentials`)
- `benchmarks/` — performance benchmarks (pytest-benchmark, not collected in CI)

## Code Conventions

- **Formatting**: black (line length 88, target py39)
- **Linting**: ruff (rules: E, F, W, I, UP, B, SIM)
- **Logging**: use `logging.getLogger(__name__)` per module. Never call `logging.basicConfig()` in library code. Use `%`-style formatting in log calls so strings are only evaluated when the log level is active.
- **Docstrings**: Sphinx-compatible `:param:` / `:return:` format
- **Imports**: standard library first, then third-party, then local. One import per line for local modules.
- **Type hints**: all public API methods must have type annotations. All source modules use `from __future__ import annotations`.
- **Return types**: request methods always return `BlestaResponse`, even on failure (`status_code=0` for network errors). Prefer `None` over `False` for "no result" returns. Avoid mixed return types (e.g., `dict | False`).
- **Context managers**: both clients support `with` / `async with` for automatic resource cleanup.

## Versioning

- **Semantic versioning** (MAJOR.MINOR.PATCH) for releases
- Version is tracked in `pyproject.toml` (`version = "X.Y.Z"`) and `CHANGELOG.md`
- `__version__` is exposed at runtime via `importlib.metadata`
- Git tags use `vX.Y.Z` format (e.g., `v0.3.0`)

## Commit Style

- Lowercase imperative messages (e.g., `add CLI tests`, `fix logging side effect`)
- No conventional commit prefixes currently enforced
- Keep messages concise and descriptive
- Never include Co-Authored-By or attribution lines in commits

## Testing

- Unit tests use `unittest.mock` (patch `requests.Session` / `httpx.AsyncClient` methods)
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- `test_credentials` is marked `@pytest.mark.integration` — requires valid `.env` credentials
- CI runs with `-m "not integration"` to skip live API tests
- CI enforces **97%+ coverage** via `--cov-fail-under=97`
- `testpaths = ["tests"]` keeps benchmarks out of CI collection

## CLI Configuration

The CLI reads from a `.env` file (via python-dotenv, requires `pip install blesta_sdk[cli]`):

```
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

The programmatic API (`BlestaRequest` / `AsyncBlestaRequest`) takes these as constructor arguments directly.

## CI/CD

- `.github/workflows/test.yml` — runs tests, black, and ruff on push/PR to master (Python 3.9/3.12/3.13 matrix)
- `.github/workflows/publish.yml` — builds and publishes to PyPI on GitHub release
- Uses `uv build` and `uv publish` with a `PYPI_TOKEN` secret

## SDK Usage Reference

When writing code that uses `blesta_sdk`, follow these patterns.

### Initialization

All API calls go through `model`/`method` pairs that map to Blesta's REST routes (`/api/model/method.json`). For plugin models, use dot notation: `"plugin.model"`.

```python
from blesta_sdk import BlestaRequest

api = BlestaRequest(
    url="https://example.com/api",
    user="api_user",
    key="api_key",
    auth_method="header",   # or "basic" (default)
    timeout=30,             # seconds, default 30
    max_retries=3,          # exponential backoff on 5xx/network errors
)
```

Or as a context manager:

```python
with BlestaRequest(url, user, key) as api:
    response = api.get("clients", "getList")
```

### Requests and Responses

```python
response = api.get("clients", "getList", {"page": 1})
response = api.post("clients", "create", {"firstname": "John", ...})
response = api.put("clients", "edit", {"client_id": 1, ...})
response = api.delete("clients", "delete", {"client_id": 1})
```

Every method returns a `BlestaResponse` — even on network failure (`status_code=0`):

```python
response.status_code   # int: HTTP status code (0 on network error)
response.data          # parsed JSON "response" field, or None
response.raw           # raw response body as str
response.errors()      # dict of errors, or None on success
response.is_json       # bool
response.is_csv        # bool
response.csv_data      # list[dict] for CSV responses, or None
```

### Pagination

```python
# Iterator (memory-efficient)
for client in api.iter_all("clients", "getList"):
    print(client["id"])

# Collect all pages into a list
all_clients = api.get_all("clients", "getList")

# Get a record count
total = api.count("clients")  # calls getListCount, returns int
```

### Batch Extraction

```python
data = api.extract([
    ("clients", "getList"),
    ("invoices", "getList"),
    ("transactions", "getList", {"status": "approved"}),
])
# data["clients.getList"] -> list of all clients
```

### Reports

```python
# Single report (returns CSV response)
response = api.get_report("tax_liability", "2025-01-01", "2025-12-31")
rows = response.csv_data  # list[dict[str, str]]

# Monthly time-series (adds "_period" key to each row)
rows = api.get_report_series("tax_liability", "2025-01", "2025-12")
```

### Async Client

The async client mirrors the sync API. Install with `pip install blesta_sdk[async]`.

```python
from blesta_sdk import AsyncBlestaRequest

async with AsyncBlestaRequest(url, user, key, auth_method="header") as api:
    response = await api.get("clients", "getList")

    # Async pagination
    async for client in api.iter_all("clients", "getList"):
        print(client["id"])

    # Concurrent batch extraction
    data = await api.extract([("clients", "getList"), ("invoices", "getList")])

    # Concurrent pagination (count-first, then parallel page fetches)
    all_items = await api.get_all_fast("invoices", "getList", batch_size=5)

    # Concurrent monthly reports
    rows = await api.get_report_series_concurrent(
        "tax_liability", "2025-01", "2025-12", max_concurrency=4
    )
```
