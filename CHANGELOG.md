# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-03-01

### Added
- `auth_method` parameter on both `BlestaRequest` and `AsyncBlestaRequest`. Set `auth_method="header"` to use Blesta's recommended header-based authentication (`BLESTA-API-USER` / `BLESTA-API-KEY` headers) instead of HTTP Basic Auth. Defaults to `"basic"` for backward compatibility.
- `get_report_series_concurrent()` on `AsyncBlestaRequest` — fetches all months in parallel via `asyncio.gather()`. Optional `max_concurrency` parameter for throttling. ~12x faster than sequential for 12-month ranges.
- `get_all_fast()` on `AsyncBlestaRequest` — count-first batched parallel pagination. Calls `getListCount` first, then fetches pages concurrently in configurable `batch_size` batches. ~8x faster than sequential for 50-page datasets.
- Concurrency benchmarks with simulated network latency (`benchmarks/test_bench_concurrency.py`). Measures real parallelism wins across report series, extraction, and pagination scenarios.

## [0.2.3] - 2026-03-01

### Fixed
- `BlestaResponse.csv_data` now caches results after first access, avoiding repeated `csv.DictReader` parsing on subsequent property reads.

### Changed
- Clarified `AsyncBlestaRequest` timeout docstring: timeout is set at client initialization and cannot be changed per-request (unlike the sync client).

## [0.2.2] - 2026-03-01

### Added
- `count()` convenience method on `BlestaRequest` for `getListCount`-style API calls. Returns a plain `int` with `0` fallback on errors.
- Connection pool tuning via `pool_connections` and `pool_maxsize` parameters on `BlestaRequest`. Defaults to 10/10 (up from requests' default 1/1), improving throughput for sequential pagination workloads.
- `AsyncBlestaRequest` async client powered by httpx. Install with `pip install blesta_sdk[async]`.
- All sync client methods available as async: `get()`, `post()`, `put()`, `delete()`, `submit()`, `count()`, `iter_all()`, `get_all()`, `extract()`, and report methods.
- `extract()` runs targets concurrently via `asyncio.gather()`.
- `iter_all()` is an async generator (`async for item in api.iter_all(...):`).
- Lazy import: `from blesta_sdk import AsyncBlestaRequest` only requires httpx when accessed.
- `[async]` optional dependency group for httpx.

### Fixed
- CLI `--last-request` flag now works on error responses (was unreachable after `sys.exit(1)`).
- `BlestaResponse.is_json` no longer re-parses JSON on every access (uses cached result).
- `BlestaResponse.raw` property type corrected to `str | None`.
- `BlestaResponse.errors()` returns clearer message for non-200 responses without an `errors` key.
- Replaced f-string logging with `%`-style formatting (avoids string evaluation when log level is disabled).
- Wrapped `conftest.py` dotenv import in `try/except` for robustness without dev deps.

### Changed
- CI enforces `--cov-fail-under=97` and `black --check`.
- Added `testpaths = ["tests"]` to prevent benchmarks from being collected in CI.
- Excluded `.claude/` and `benchmarks/` from sdist.
- Added Python 3.10/3.11 classifiers to `pyproject.toml`.
- Updated CLAUDE.md and README to reflect current project structure and full API surface.

### Removed
- Unreachable dead code in `iter_all()` (both sync and async clients).
- Stale `dist/` build artifacts from repository.
- Redundant `@pytest.mark.asyncio` decorators (covered by `asyncio_mode = "auto"`).

## [0.2.1] - 2026-03-01

### Added
- `__repr__` on `BlestaRequest` and `BlestaResponse` for readable REPL/notebook output.
- `max_retries` parameter on `BlestaRequest` — automatic retry with exponential backoff for network errors and 5xx responses.
- `extract()` method for batch extraction of multiple paginated endpoints in one call.
- README updated to position SDK as a data extraction/integration tool for Blesta instances.

## [0.2.0] - 2026-03-01

### Breaking Changes
- **Flattened package structure** — removed `api/`, `core/`, and `cli/` subpackages. Import directly: `from blesta_sdk import BlestaRequest, BlestaResponse`.
- Renamed `response.response` property to `response.data`.
- Renamed `get_all_pages()` to `iter_all()`.
- Network errors now return `status_code=0` instead of `500`.
- Removed deprecated `response_code` property (use `status_code`).
- `python-dotenv` moved from runtime dependency to optional `[cli]` extra. Install with `pip install blesta_sdk[cli]` for `.env` file support.

### Added
- CSV response detection: `BlestaResponse.is_json`, `is_csv`, and `csv_data` properties.
- Pagination: `BlestaRequest.iter_all()` generator and `get_all()` list helper.
- Report helper: `BlestaRequest.get_report()` with automatic `vars[]` parameter formatting.
- Time-series reports: `get_report_series()` and `get_report_series_pages()` for monthly date ranges.
- Optional pandas integration: `BlestaResponse.to_dataframe()` for CSV and JSON responses.
- `py.typed` marker for PEP 561 type-checking support.
- PyPI classifiers, project URLs, and `[tool.black]`/`[tool.ruff]` configuration.
- Hatch sdist excludes to keep CI, tests, and lockfiles out of distributions.
- CI test workflow (`.github/workflows/test.yml`) with Python 3.9/3.12/3.13 matrix.

### Fixed
- HTTP status codes now pass through correctly (401/403/404 were previously reported as 500).
- CSV responses no longer trigger false "Invalid JSON response" errors.
- `_format_response()` handles `None` body without raising `TypeError`.
- CLI now returns exit code 1 on missing credentials and API errors.
- Moved `load_dotenv()` inside `cli()` to prevent side effects on import.
- Removed `black` from runtime dependencies.
- CLI error output is now valid JSON (was Python repr).

### Changed
- Internal modules renamed to `_client.py`, `_response.py`, `_dateutil.py`, `_cli.py`.
- `submit()` action parameter uses `Literal["GET", "POST", "PUT", "DELETE"]` typing.
- `__all__` includes `__version__`.
- Upgraded publish workflow to `actions/checkout@v4` and `actions/setup-python@v5`.
- Pinned all dependencies to latest compatible versions.
- README fully rewritten with complete API reference, usage examples, and CLI documentation.

### Removed
- `examples/` directory (covered in README).
- `api/`, `core/`, `cli/` subpackage `__init__.py` files.
- `tests/__init__.py`.

### Migration from 0.1.x
- `from blesta_sdk.api import BlestaRequest` → `from blesta_sdk import BlestaRequest`
- `from blesta_sdk.core import BlestaResponse` → `from blesta_sdk import BlestaResponse`
- `response.response` → `response.data`
- `response.response_code` → `response.status_code`
- `get_all_pages()` → `iter_all()`
- `pip install blesta_sdk` → `pip install blesta_sdk[cli]` (if using `.env` files)

## [0.1.7] - 2026-02-28

### Fixed
- Fixed CLI command name in README and examples (`blesta-cli` → `blesta`).
- Fixed `--last-request` description in README (it displays request info, does not replay).
- Fixed changelog version typo (`1.5.0` → `0.1.5`).
- Fixed `logging.basicConfig()` side effect in `blesta_request.py` — now uses module-level logger.

### Added
- Python API usage examples in README.
- Full CLI test coverage (missing credentials, success, error, params, `--last-request`).
- Tests for `BlestaResponse.response_code`, `errors()` returning `False`, and missing response key.
- `CLAUDE.md` project conventions file.

### Changed
- Updated README setup instructions to include `uv` and Python version requirement.
- Updated README project structure tree to include `.github/`, `CHANGELOG.md`.

## [0.1.6] - 2025-02-28

### Changed
- Updated `requires-python` to `>=3.9` to ensure compatibility with dependencies.
- Removed `indexes` field from `pyproject.toml` and used `index-url` and `publish-url` directly.

## [0.1.5] - 2025-02-28

### Added
- Initial implementation of `BlestaRequest` class for making API requests.
- Initial implementation of `BlestaResponse` class for handling API responses.
- Unit tests for `BlestaRequest` class methods: `get`, `post`, `put`, `delete`, `submit`, `get_last_request`.
- Unit tests for `BlestaResponse` class methods: `response`, `response_code`, `raw`, `status_code`, `errors`.

### Changed
- Updated `BlestaResponse` class to handle invalid JSON responses correctly.
- Improved error handling in `BlestaResponse` class.

### Fixed
- Fixed issue with `BlestaResponse` class where `errors` method returned incorrect structure for invalid JSON responses.

## [0.1.4] - 2025-01-20

- Packaging and dependency fixes.

## [0.1.3] - 2025-01-20 [YANKED]

## [0.1.2] - 2025-01-20 [YANKED]

## [0.1.1] - 2025-01-19 [YANKED]

## [0.1.0] - 2025-01-19

### Added
- Initial release of `blesta_sdk` package.
- Basic functionality for making API requests to Blesta API.
- Environment variable support for API URL, user, and key.
- Basic unit tests for API request and response handling.
