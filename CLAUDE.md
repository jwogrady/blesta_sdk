# CLAUDE.md — Project Conventions for blesta_sdk

## Project Overview

Python SDK and CLI for the Blesta billing platform REST API. Wraps HTTP requests with Basic Auth and provides structured response handling, automatic pagination, batch extraction, and optional async support.

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
uv run pytest -m "not integration"         # Run tests without live API calls
uv run pytest --cov=blesta_sdk --cov-report=term-missing --cov-fail-under=97  # Run with coverage
uv run black src/ tests/                   # Format code
uv run ruff check src/ tests/              # Lint
uv build                                   # Build package
```

## Project Structure

- `src/blesta_sdk/__init__.py` — public API surface, lazy import for `AsyncBlestaRequest`
- `src/blesta_sdk/_client.py` — `BlestaRequest`: sync HTTP client (GET/POST/PUT/DELETE, pagination, reports)
- `src/blesta_sdk/_async_client.py` — `AsyncBlestaRequest`: async HTTP client (mirrors sync API)
- `src/blesta_sdk/_response.py` — `BlestaResponse`: response parsing, CSV/JSON detection, error extraction
- `src/blesta_sdk/_dateutil.py` — internal date range utilities for time-series reports
- `src/blesta_sdk/_cli.py` — CLI entry point (registered as `blesta` in pyproject.toml)
- `tests/` — unit tests (mocked) + one live integration test (`test_credentials`)
- `benchmarks/` — performance benchmarks (pytest-benchmark, not collected in CI)

## Code Conventions

- **Formatting**: black (default settings)
- **Linting**: ruff
- **Logging**: use `logging.getLogger(__name__)` per module. Never call `logging.basicConfig()` in library code. Use `%`-style formatting in log calls (not f-strings).
- **Docstrings**: use `:param:` / `:return:` style (Sphinx-compatible)
- **Imports**: standard library first, then third-party, then local. One import per line for local modules.
- **Type hints**: all public API methods should have type annotations. Use `from __future__ import annotations` for forward references.
- **Type returns**: `BlestaResponse` is always returned from request methods, even on failure (with status 0 for network errors).
- **Return types**: prefer `None` over `False` for "no result" returns. Avoid mixed return types (e.g., `dict | False`).

## Versioning

- **Semantic versioning** (MAJOR.MINOR.PATCH) for releases
- Version is tracked in `pyproject.toml` (`version = "X.Y.Z"`) and `CHANGELOG.md`
- `__version__` is exposed at runtime via `importlib.metadata`
- Git tags use `vX.Y.Z` format (e.g., `v0.2.2`)

## Commit Style

- Lowercase imperative messages (e.g., `add CLI tests`, `fix logging side effect`)
- No conventional commit prefixes currently enforced
- Keep messages concise and descriptive
- Never include Co-Authored-By or attribution lines in commits

## Testing

- Unit tests use `unittest.mock` (patch the `requests.Session` / `httpx.AsyncClient` methods)
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
- `test_credentials` is marked `@pytest.mark.integration` — requires valid `.env` credentials
- CI runs with `-m "not integration"` to skip live API tests
- CI enforces **97%+ coverage** via `--cov-fail-under=97`
- `testpaths = ["tests"]` keeps benchmarks out of CI collection

## Configuration

The CLI reads from a `.env` file (via python-dotenv, requires `pip install blesta_sdk[cli]`):

```
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

The programmatic API (`BlestaRequest`) takes these as constructor arguments directly.

## CI/CD

- `.github/workflows/test.yml` — runs tests, black, and ruff on push/PR to master (Python 3.9/3.12/3.13 matrix)
- `.github/workflows/publish.yml` — builds and publishes to PyPI on GitHub release
- Uses `uv build` and `uv publish` with a `PYPI_TOKEN` secret
