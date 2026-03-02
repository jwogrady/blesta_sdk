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
uv run black src/ tests/ tools/             # Format code
uv run ruff check src/ tests/ tools/       # Lint
uv build                                   # Build package
```

## Project Structure

- `src/blesta_sdk/__init__.py` — public API exports (`__all__`), lazy import for `AsyncBlestaRequest`
- `src/blesta_sdk/_client.py` — `BlestaRequest`: sync HTTP client (GET/POST/PUT/DELETE, pagination, reports, batch extraction, schema-aware calls)
- `src/blesta_sdk/_async_client.py` — `AsyncBlestaRequest`: async HTTP client (mirrors sync API, adds `get_all_fast()` and `get_report_series_concurrent()`)
- `src/blesta_sdk/_response.py` — `BlestaResponse`: response parsing, CSV/JSON detection, error extraction, DataFrame conversion
- `src/blesta_sdk/_discovery.py` — `BlestaDiscovery` and `MethodSpec`: schema-driven API introspection (lazy-loaded)
- `src/blesta_sdk/_dateutil.py` — internal date range utilities for time-series reports
- `src/blesta_sdk/_cli.py` — CLI entry point (registered as `blesta` in pyproject.toml)
- `schemas/` — bundled JSON schemas (core: 63 models, plugin: 8 models) used by `BlestaDiscovery`
- `tools/` — schema extraction utilities (`extract_schema.py`, `extract_plugin_schema.py`, `_classify.py`)
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

## SDK Usage

See `SDK_USAGE.md` for detailed patterns and examples when writing code that uses this SDK (initialization, requests, pagination, reports, discovery, async client, etc.).
