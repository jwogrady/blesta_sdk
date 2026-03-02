# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-03-01

### Added
- `on_error` parameter on `get_all()` (sync and async). Passes through to `iter_all()` so callers can use `on_error="raise"` to get `PaginationError` with partial results instead of silent truncation. Defaults to `"warn"` (backward-compatible).

### Fixed
- Async `extract()` now gates concurrent targets through the client-level semaphore (`max_concurrency`), preventing request storms for large target lists. Previously, all targets were launched simultaneously with no concurrency limit.

## [0.5.0] - 2026-03-01

### Added
- `PaginationError` exception with `page`, `status_code`, and `partial_items` attributes. Raised by `iter_all()` when `on_error="raise"` and a non-200 response is received during pagination. Exported from `blesta_sdk` package.
- `on_error` parameter on `iter_all()` and `iter_pages()` (sync and async). `"raise"` raises `PaginationError` with partial results; `"warn"` (default) logs and stops — backward-compatible.
- `max_pages` parameter on `iter_all()`, `get_all()`, and `iter_pages()` (sync and async) to cap the number of pages fetched.
- `iter_pages()` method on both clients — yields each page as a separate list for batch-flushing workflows.
- `retry_mutations` parameter on both clients. When `False` (default), only GET and DELETE are retried. Prevents accidental double-creates.
- `max_concurrency` parameter on `AsyncBlestaRequest` — shared `asyncio.Semaphore` (default 10) limiting concurrent requests across `get_all_fast()`, `extract()`, and `get_report_series_concurrent()`.
- `verify` parameter on `get_all_fast()` — re-counts after fetching and logs a warning on TOCTOU mismatch.
- `free_raw()` method on `BlestaResponse` — releases raw text to save memory while preserving parsed data.
- Repeat page detection in `iter_all()` and `iter_pages()` — aborts after 3 consecutive identical pages to prevent infinite loops.

### Changed
- Retry backoff now includes jitter (`base_delay * (0.5 + random() * 0.5)`) to prevent thundering herd.
- `get_report_series()` / `get_report_series_concurrent()` no longer mutate cached `csv_data` row dicts when adding `_period` keys.
- `get_report_series_concurrent()` and `get_all_fast()` use the client-level semaphore by default.
- `call()` and `count_for()` use a cached `BlestaDiscovery` instance per client.
- Async `submit()` stores `_last_request` in a `ContextVar` for per-task isolation.
- Extracted shared `validate_segment()` helper into `_validation.py` to eliminate duplicated URL validation logic between sync and async clients.

### Fixed
- POST and PUT requests are no longer retried by default — only idempotent methods (GET, DELETE) are retried.
- `get_report_series()` no longer mutates `BlestaResponse.csv_data` cache when appending `_period` keys.
- Async `get_last_request()` reads from `ContextVar` first, preventing race conditions in concurrent tasks.
- `BlestaDiscovery` is no longer re-instantiated on every `call()` / `count_for()` invocation.
- `iter_pages()` now has safety parity with `iter_all()` (repeat-page detection, `on_error` support).

## [0.4.0] - 2026-03-01

### Added
- `BlestaDiscovery` — schema-driven API discovery module. Loads bundled JSON schemas (63 core models, 8 plugin models) and exposes `list_models()`, `list_methods()`, `get_method_spec()`, `resolve_http_method()`, and `suggest_pagination_pair()`.
- `MethodSpec` frozen dataclass returned by `get_method_spec()` with model, method, http_method, category, description, params, return_type, source, and signature fields.
- `generate_capabilities_report(format="markdown"|"json")` for full API surface reports.
- `generate_ai_index(path)` writes JSONL index suitable for embedding pipelines.
- `call(model, method, args=None, action=None)` on both `BlestaRequest` and `AsyncBlestaRequest` — schema-aware request that infers the HTTP method from the bundled schema. When the schema cannot resolve the method, falls back to a prefix-based heuristic (`get*` -> GET, `create*` -> POST, `edit*` -> PUT, `delete*` -> DELETE). Logs a warning and defaults to POST only when the method name is truly ambiguous.
- `call_all(model, method, args=None, start_page=1)` — schema-aware pagination convenience wrapper.
- `count_for(model, list_method="getList", args=None)` — auto-discovers the count method via schema pagination pairs. Falls back to `list_method + "Count"`.
- `BlestaDiscovery` and `MethodSpec` exported from `blesta_sdk` package `__init__.py`.
- Comprehensive test suites for discovery module, call helpers, and schema tooling I/O layers.
- Schema extractor I/O layer tests (mocked `build_schema()`, `main()` CLI for both core and plugin extractors).

### Changed
- **Schemas now bundled inside the package** (`src/blesta_sdk/schemas/`) and loaded via `importlib.resources`. `BlestaDiscovery` works out of the box in pip-installed wheels — no source checkout required.
- `_discovery.py` loads bundled schemas via `importlib.resources` instead of filesystem traversal. Custom schema paths via `core_schema_path`/`plugin_schema_path` constructor args still work.
- `Development Status` classifier upgraded from `3 - Alpha` to `4 - Beta`.
- CI workflow now lints `tools/` directory alongside `src/` and `tests/`.
- `__getattr__` in `__init__.py` now has explicit `-> object` return type annotation.
- README rewritten with complete v0.4.0 API reference including discovery, schema-aware helpers, authentication section, and async-specific method documentation.
- README API reference table now includes `submit()`, `call()`, `call_all()`, `count_for()`, and `auth_method` constructor parameter.
- README `AsyncBlestaRequest` section now documents `get_all_fast()` and `get_report_series_concurrent()`.
- Publish workflow simplified to token-based auth only (removed unused OIDC `id-token` permission).

### Fixed
- `call()` no longer silently defaults all requests to POST when schemas are unavailable. Now uses method-name heuristics for correct HTTP verb inference.
- `is_csv` property now short-circuits on empty/whitespace responses before attempting JSON parse, avoiding unnecessary work.
- `iter_all()` (sync and async) avoids redundant variable assignment when args is `None`.
- Schema tooling test coverage increased from 73% to 98%.
- README pool defaults description corrected (removed inaccurate "up from requests' default of 1/1" claim).
- `__version__` now documented in README API reference.

## [0.3.0] - 2026-03-01

### Added
- `AsyncBlestaRequest` async client powered by httpx. Install with `pip install blesta_sdk[async]`.
- All sync client methods available as async: `get()`, `post()`, `put()`, `delete()`, `submit()`, `count()`, `iter_all()`, `get_all()`, `extract()`, and report methods.
- `get_report_series_concurrent()` on `AsyncBlestaRequest` — fetches all months in parallel via `asyncio.gather()`. Optional `max_concurrency` parameter for throttling.
- `get_all_fast()` on `AsyncBlestaRequest` — count-first batched parallel pagination. Calls `getListCount` first, then fetches pages concurrently in configurable `batch_size` batches.
- Async `extract()` runs targets concurrently via `asyncio.gather()`.
- `iter_all()` is an async generator (`async for item in api.iter_all(...):`).
- Lazy import: `from blesta_sdk import AsyncBlestaRequest` only requires httpx when accessed.
- `[async]` optional dependency group for httpx.
- `auth_method` parameter on both `BlestaRequest` and `AsyncBlestaRequest`. Set `auth_method="header"` to use header-based authentication (`BLESTA-API-USER` / `BLESTA-API-KEY` headers) instead of HTTP Basic Auth. Defaults to `"basic"` for backward compatibility.
- `count()` convenience method on `BlestaRequest` for `getListCount`-style API calls. Returns a plain `int` with `0` fallback on errors.
- Connection pool tuning via `pool_connections` and `pool_maxsize` parameters on `BlestaRequest`. Defaults to 10/10.
- `__repr__` on `BlestaRequest` and `BlestaResponse` for readable REPL/notebook output.
- `max_retries` parameter on `BlestaRequest` — automatic retry with exponential backoff for network errors and 5xx responses.
- `extract()` method on `BlestaRequest` for batch extraction of multiple paginated endpoints in one call.
- Concurrency benchmarks with simulated network latency (`benchmarks/`).

### Fixed
- `BlestaResponse.csv_data` now caches results after first access, avoiding repeated `csv.DictReader` parsing on subsequent property reads.
- `BlestaResponse.is_json` no longer re-parses JSON on every access (uses cached result).
- `BlestaResponse.raw` property type corrected to `str | None`.
- `BlestaResponse.errors()` returns clearer message for non-200 responses without an `errors` key.
- CLI `--last-request` flag now works on error responses (was unreachable after `sys.exit(1)`).
- Replaced f-string logging with `%`-style formatting (avoids string evaluation when log level is disabled).
- Wrapped `conftest.py` dotenv import in `try/except` for robustness without dev deps.

### Changed
- CI enforces `--cov-fail-under=97` and `black --check`.
- Added `testpaths = ["tests"]` to prevent benchmarks from being collected in CI.
- Excluded `.claude/` and `benchmarks/` from sdist.
- Added Python 3.10/3.11 classifiers to `pyproject.toml`.
- Clarified `AsyncBlestaRequest` timeout docstring.
- Updated CLAUDE.md and README to reflect current project structure and full API surface.

### Removed
- Unreachable dead code in `iter_all()` (both sync and async clients).
- Stale `dist/` build artifacts from repository.
- Redundant `@pytest.mark.asyncio` decorators (covered by `asyncio_mode = "auto"`).

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
