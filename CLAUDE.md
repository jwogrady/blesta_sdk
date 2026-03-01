# CLAUDE.md — Project Conventions for blesta_sdk

## Project Overview

Python SDK and CLI for the Blesta billing platform REST API. Wraps HTTP requests with Basic Auth and provides structured response handling.

## Tech Stack

- **Python** >= 3.9
- **Build**: hatchling (via `uv`)
- **Dependencies**: requests, python-dotenv
- **Dev tools**: pytest, pytest-cov, black, ruff

## Common Commands

```bash
uv sync                                    # Install all dependencies
uv run pytest -v                           # Run tests
uv run pytest -m "not integration"         # Run tests without live API calls
uv run pytest --cov=blesta_sdk --cov-report=term-missing  # Run with coverage
uv run black src/ tests/                   # Format code
uv run ruff check src/ tests/              # Lint
uv build                                   # Build package
```

## Project Structure

- `src/blesta_sdk/api/` — `BlestaRequest`: HTTP client (GET/POST/PUT/DELETE)
- `src/blesta_sdk/core/` — `BlestaResponse`: response parsing and error extraction
- `src/blesta_sdk/cli/` — CLI entry point (registered as `blesta` in pyproject.toml)
- `tests/` — unit tests (mocked) + one live integration test (`test_credentials`)

## Code Conventions

- **Formatting**: black (default settings)
- **Linting**: ruff
- **Logging**: use `logging.getLogger(__name__)` per module. Never call `logging.basicConfig()` in library code.
- **Docstrings**: use `:param:` / `:return:` style (Sphinx-compatible)
- **Imports**: standard library first, then third-party, then local. One import per line for local modules.
- **Type hints**: all public API methods should have type annotations. Use `from __future__ import annotations` for forward references.
- **Type returns**: `BlestaResponse` is always returned from request methods, even on failure (with status 500).
- **Return types**: prefer `None` over `False` for "no result" returns. Avoid mixed return types (e.g., `dict | False`).

## Versioning

- **Semantic versioning** (MAJOR.MINOR.PATCH) for releases
- Version is tracked in `pyproject.toml` (`version = "X.Y.Z"`) and `CHANGELOG.md`
- `__version__` is exposed at runtime via `importlib.metadata`
- Git tags use `vX.Y.Z` format (e.g., `v0.1.7`)

## Commit Style

- Lowercase imperative messages (e.g., `add CLI tests`, `fix logging side effect`)
- No conventional commit prefixes currently enforced
- Keep messages concise and descriptive
- Never include Co-Authored-By or attribution lines in commits

## Testing

- Unit tests use `unittest.mock` (patch the `requests.Session` methods)
- `test_credentials` is marked `@pytest.mark.integration` — requires valid `.env` credentials
- CI runs with `-m "not integration"` to skip live API tests
- Target **98%+ coverage** (only `if __name__ == "__main__"` guards excluded)

## Configuration

The CLI reads from a `.env` file (via python-dotenv):

```
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

The programmatic API (`BlestaRequest`) takes these as constructor arguments directly.

## CI/CD

- `.github/workflows/test.yml` — runs tests and linting on push/PR to main (Python 3.9/3.12/3.13 matrix)
- `.github/workflows/publish.yml` — builds and publishes to PyPI on GitHub release
- Uses `uv build` and `uv publish` with a `PYPI_TOKEN` secret
