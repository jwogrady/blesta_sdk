# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
uv sync                                                          # Install all dependencies
uv run pytest -v                                                 # Run all unit tests
uv run pytest tests/test_blesta_sdk.py::TestClassName::test_name -v  # Run a single test
uv run pytest -k "pattern" -v                                    # Run tests matching a pattern
uv run pytest -m "not integration"                               # Skip live API integration tests
uv run pytest -m integration -v                                  # Run live integration test (requires .env)
uv run pytest --cov=blesta_sdk --cov-report=term-missing --cov-fail-under=97  # Coverage check
uv run black src/ tests/ tools/                                  # Format code
uv run ruff check src/ tests/ tools/                             # Lint
uv build                                                         # Build package
uv run pytest benchmarks/ -v --benchmark-only                   # Run benchmarks (excluded from CI)
uv run python tools/extract_schema.py                           # Re-extract core schemas → src/blesta_sdk/schemas/
uv run python tools/extract_plugin_schema.py                    # Re-extract plugin schemas → src/blesta_sdk/schemas/
```

## Project Structure

- `src/blesta_sdk/__init__.py` — public API exports (`__all__`), lazy import for `AsyncBlestaRequest`
- `src/blesta_sdk/_client.py` — `BlestaRequest`: sync HTTP client (GET/POST/PUT/DELETE, `submit()`, `call()`, `call_all()`, `count_for()`, pagination, reports, batch extraction)
- `src/blesta_sdk/_async_client.py` — `AsyncBlestaRequest`: async HTTP client (mirrors sync API, adds `get_all_fast()` and `get_report_series_concurrent()`)
- `src/blesta_sdk/_response.py` — `BlestaResponse`: response parsing, CSV/JSON detection, error extraction, `raise_for_status()`, DataFrame conversion
- `src/blesta_sdk/_pagination.py` — `PaginationState`: shared pagination logic with stuck-page and alternating-loop cycle detection; used by both sync and async clients
- `src/blesta_sdk/_redaction.py` — `redact_args()`: shared sensitive-key scrubber used by both clients for `get_last_request()` output
- `src/blesta_sdk/_discovery.py` — `BlestaDiscovery` and `MethodSpec`: schema-driven API introspection (lazy-loaded)
- `src/blesta_sdk/_exceptions.py` — typed exception hierarchy: `BlestaError`, `BlestaConnectionError`, `BlestaAPIError`, `BlestaAuthError`, `BlestaRateLimitError` (`.retry_after`), `BlestaServerError`, `PaginationError`
- `src/blesta_sdk/_env_config.py` — `BlestaEnvConfig`: environment-keyed credential resolution (`dev`/`stage`/`live`) with no cross-env fallback
- `src/blesta_sdk/_validation.py` — shared URL segment validation used by both clients
- `src/blesta_sdk/_dateutil.py` — `_month_boundaries()` for time-series report date ranges
- `src/blesta_sdk/_cli.py` — CLI entry point (registered as `blesta` in pyproject.toml)
- `src/blesta_sdk/schemas/` — **canonical** bundled JSON schemas (core: 63 models, plugin: 8 models) used by `BlestaDiscovery`. Do not edit the deprecated root-level `schemas/` copies.
- `tools/` — schema extraction utilities (`extract_schema.py`, `extract_plugin_schema.py`, `_classify.py`); write to `src/blesta_sdk/schemas/` by default
- `tests/` — unit tests (mocked) + one live integration test (`test_credentials`)
- `benchmarks/` — performance benchmarks (pytest-benchmark, not collected in CI)

## Architecture: Cross-Cutting Patterns

**All requests return `BlestaResponse`** — never raw dicts or `False`. Network errors produce `status_code=0`. Callers check `response.ok`, `response.data`, or call `response.raise_for_status()` to get typed exceptions.

**HTTP 200 ≠ success** — Blesta returns HTTP 200 with an `errors` key for validation failures. Always check `response.errors` or `response.ok`, not just the status code.

**Pagination** is handled by `PaginationState` (shared between `_client.py` and `_async_client.py`). It detects stuck pages (3 consecutive identical pages) and alternating loops, raising `PaginationError` rather than looping forever.

**Retry logic** in both clients respects the `Retry-After` response header on 429s. If the header is present and non-zero, the client sleeps for that many seconds instead of using exponential backoff.

**`get_last_request()`** returns a redacted copy of the last request's args (sensitive keys replaced with `"***"` by `redact_args()` in `_redaction.py`). The actual HTTP request is never modified. In async context, this is per-asyncio-task via `ContextVar`.

**Schema-aware calls** (`call()`, `call_all()`, `count_for()`) use bundled schemas to infer the correct HTTP method from the model/method name, falling back to prefix heuristics (`get*` → GET, `add*`/`create*` → POST, etc.).

**`BlestaEnvConfig`** resolves credentials from constructor kwargs first, then `BLESTA_{ENV}_URL/USER/KEY` env vars where `{ENV}` is `DEV`, `STAGE`, or `LIVE`. No cross-environment fallback — `live` credentials are never read when `stage` is requested.

**Discovery lazy-loading** — `BlestaDiscovery` loads and parses the bundled schema JSON on first use, not at import time, to keep import cost low.

## Code Conventions

- **Formatting**: black (line length 88, target py39)
- **Linting**: ruff (rules: E, F, W, I, UP, B, SIM)
- **Logging**: `logging.getLogger(__name__)` per module; never `logging.basicConfig()` in library code; `%`-style format strings only
- **Docstrings**: Sphinx-compatible `:param:` / `:return:` format
- **Imports**: stdlib → third-party → local; one import per line for local modules
- **Type hints**: all public API methods annotated; all source modules use `from __future__ import annotations`
- **Return types**: request methods always return `BlestaResponse`. Prefer `None` over `False` for "no result". No mixed return types (e.g. `dict | False`).
- **Context managers**: both clients support `with` / `async with` for resource cleanup

## Versioning

- Semantic versioning (MAJOR.MINOR.PATCH); version in `pyproject.toml` and `CHANGELOG.md`
- `__version__` exposed at runtime via `importlib.metadata`
- Git tags: `vX.Y.Z`

## Commit Style

- Lowercase imperative messages (`add CLI tests`, `fix logging side effect`)
- No conventional commit prefixes
- No Co-Authored-By or attribution lines

## Testing

- Unit tests use `unittest.mock` (patch `requests.Session` / `httpx.AsyncClient`)
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` decorator needed)
- `test_credentials` is `@pytest.mark.integration` — requires valid `.env` credentials
- CI skips integration tests (`-m "not integration"`) and enforces **97%+ coverage**
- `testpaths = ["tests"]` keeps benchmarks out of CI collection

## CLI Configuration

The `blesta` CLI reads from `.env` (requires `pip install blesta_sdk[cli]`):

```
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

The `--last-request` CLI flag returns a redacted args dict (sensitive values shown as `"***"`). The programmatic API takes credentials as constructor arguments directly.

## CI/CD

- `.github/workflows/test.yml` — tests, black, ruff on push/PR to master (Python 3.9/3.12/3.13 matrix)
- `.github/workflows/publish.yml` — builds and publishes to PyPI on GitHub release via `uv build` / `uv publish` with `PYPI_TOKEN`

## SDK Usage

See `SDK_USAGE.md` for detailed patterns and examples (initialization, requests, pagination, reports, discovery, async client, etc.).
