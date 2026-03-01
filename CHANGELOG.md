# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Breaking:** Renamed `response.response` property to `response.data`.
- **Breaking:** Renamed `get_all_pages()` to `iter_all()`.
- **Breaking:** Network errors now return `status_code=0` instead of `500`.
- **Breaking:** Removed deprecated `response_code` property (use `status_code`).
- CLI error output is now JSON (was Python repr).
- CLI missing-credentials message updated and now outputs JSON.
- `submit()` action parameter uses `Literal["GET", "POST", "PUT", "DELETE"]` typing.
- `__all__` includes `__version__`.

### Fixed
- `_format_response()` now handles `None` body without raising `TypeError`.
- CLI errors are now valid JSON, matching the documented output contract.

## [0.5.0] - 2026-03-01

### Changed
- **Breaking:** Flattened package structure — removed `api/`, `core/`, and `cli/` subpackages. Import from `blesta_sdk` directly: `from blesta_sdk import BlestaRequest, BlestaResponse`.
- Internal modules renamed to `_client.py`, `_response.py`, `_dateutil.py`, `_cli.py` (private, do not import directly).
- Shared test fixture extracted to `tests/conftest.py`.

### Removed
- `examples/` directory (CLI examples already covered in README).
- Three re-export `__init__.py` files (one per former subpackage).

### Migration
- `from blesta_sdk.api import BlestaRequest` → `from blesta_sdk import BlestaRequest`
- `from blesta_sdk.core import BlestaResponse` → `from blesta_sdk import BlestaResponse`
- `from blesta_sdk import BlestaRequest, BlestaResponse` (added in 0.4.0) continues to work unchanged.

## [0.4.0] - 2026-03-01

### Fixed
- Removed `black` from runtime dependencies (was incorrectly listed as a production dependency).
- CLI now returns exit code 1 on missing credentials and API errors (previously always exited 0).
- Moved `load_dotenv()` from module-level to inside `cli()` to prevent side effects on import.
- Replaced production URL in test fixtures with `test.example.com`.

### Added
- Top-level exports: `from blesta_sdk import BlestaRequest, BlestaResponse` now works directly.
- `py.typed` marker for PEP 561 type-checking support.
- PyPI classifiers (development status, license, Python versions, OS).
- Project URLs (repository, changelog, issues) in package metadata.
- Explicit `black` and `ruff` configuration in `pyproject.toml`.
- Hatch sdist excludes to keep CI, tests, and lockfiles out of distribution.

### Changed
- Package description updated to "Python SDK and CLI for the Blesta billing platform REST API".
- `cli` submodule no longer imported at package load (reduces import overhead and side effects).
- Upgraded `publish.yml` GitHub Actions to `actions/checkout@v4` and `actions/setup-python@v5`.

### Removed
- Unnecessary `tests/__init__.py`.

## [0.3.0] - 2026-02-28

### Added
- Time-series report helper: `BlestaRequest.get_report_series()` collects monthly report data across a date range into a flat list with `_period` metadata.
- Generator variant: `BlestaRequest.get_report_series_pages()` yields `(period, response)` tuples for memory-efficient iteration over monthly reports.
- Optional pandas integration: `BlestaResponse.to_dataframe()` converts CSV or JSON responses to pandas DataFrames (requires pandas to be installed separately).
- Internal `_month_boundaries()` date range utility for generating monthly date intervals.

## [0.2.0] - 2026-02-28

### Fixed
- HTTP status codes now pass through correctly. Previously 401/403/404 responses were reported as 500 due to `raise_for_status()` swallowing the real status code.
- CSV responses (e.g., from `report_manager/fetchAll`) no longer trigger false "Invalid JSON response" errors.

### Added
- CSV response detection: `BlestaResponse.is_json`, `is_csv`, and `csv_data` properties for automatic format handling.
- Pagination: `BlestaRequest.get_all_pages()` generator and `get_all()` list helper for auto-paginating through API results.
- Report helper: `BlestaRequest.get_report()` for fetching Blesta reports with proper `vars[]` parameter formatting.

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
