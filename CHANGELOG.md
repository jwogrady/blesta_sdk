# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **CLI credential resolution centralised** — `_build_cli_client()` helper added to
  `blesta_sdk.cli.formatters`; all four CLI surfaces (`call`, `extract`, `report`,
  `app._run_legacy`) now use it instead of duplicating the same 17-line credential/client
  block. No behaviour change.

### Fixed

- **`cli/app.py` docstring** — `_run_legacy()` docstring incorrectly claimed it delegated
  to `blesta_sdk._cli.cli`. It has always been an independent implementation; the docstring
  is now accurate.
- **`CLI_USAGE.md`** — `BLESTA_ALLOW_HTTP` was missing from the env-var reference table.
  Added with default, accepted values, and a note that HTTPS is enforced by default.

## [0.8.1] - 2026-05-27

### Fixed

- **MCP tool error handling** — API-calling tools (`blesta_call`, `blesta_get_all`,
  `blesta_extract`, `blesta_count`, `blesta_get_report`, `blesta_get_report_series`) now
  catch all exceptions (including `RuntimeError` from missing credentials) and return a
  structured `{"ok": false, "error": "..."}` JSON response instead of raising an unhandled
  exception that would surface as a raw Python traceback in MCP clients.
- **`blesta-mcp` startup error** — when the `mcp` package is not installed, `blesta-mcp`
  now prints a single-line user-friendly error message to stderr and exits with code 1,
  instead of showing a confusing chained Python traceback.

### Changed

- **`blesta_call` tool description** updated to explicitly note that passing
  `action="POST"`, `"PUT"`, or `"DELETE"` performs a mutation and that mutations are
  **not idempotent** — the caller is responsible for deduplication.
- **MCP prompt templates** — all 5 prompts now include a write-safety ``Note:`` section.
  Previously only `blesta_reconcile_invoices` had a write-safety note; the other four
  (`blesta_audit_client`, `blesta_plan_migration`, `blesta_extract_customer_snapshot`,
  `blesta_map_to_prime_account`) now state they are read-only by default and that the
  SDK does not provide idempotency for billing writes.
- `blesta_sdk.mcp.prompts` module docstring updated to document the read-only default
  and the requirement to confirm mutations with the user.

## [0.8.0] - 2026-05-27

### Added

- **`blesta_sdk.core` namespace** — canonical sub-package for core SDK classes. All public
  names remain importable from the top-level `blesta_sdk` package (backward-compatible).
  New canonical paths: `blesta_sdk.core.client.BlestaRequest`,
  `blesta_sdk.core.async_client.AsyncBlestaRequest`,
  `blesta_sdk.core.config.BlestaEnvConfig`,
  `blesta_sdk.core.response.BlestaResponse`,
  `blesta_sdk.core.errors.*`, `blesta_sdk.core.pagination.PaginationState`.
- **`blesta_sdk.discovery` namespace** — canonical sub-package for schema discovery.
  `blesta_sdk.discovery.registry` is now the canonical home for `BlestaDiscovery` and
  `MethodSpec` (previously `blesta_sdk._discovery`).
- **`blesta_sdk.cli` namespace** — CLI refactored into a sub-package with argparse
  subcommands: `call`, `extract`, `report`, and `discover`. The legacy
  `--model/--method` form remains fully supported. New `blesta_sdk.cli.commands`
  package contains individual command modules; `blesta_sdk.cli.formatters` provides
  JSON, JSONL, and CSV output helpers.
- **`blesta_sdk.mcp` namespace** — new MCP (Model Context Protocol) server surface.
  Requires `pip install blesta_sdk[mcp]` and Python 3.10+. Exposes the full Blesta
  API as 10 tools, 7 resources, and 5 prompt templates via FastMCP.
  - **Tools:** `blesta_call`, `blesta_get_all`, `blesta_extract`, `blesta_count`,
    `blesta_get_report`, `blesta_get_report_series`, `blesta_list_models`,
    `blesta_list_methods`, `blesta_get_method_spec`, `blesta_capabilities_report`.
  - **Resources:** `blesta://schema/core`, `blesta://schema/plugin`,
    `blesta://models`, `blesta://models/{model}`,
    `blesta://models/{model}/methods/{method}`,
    `blesta://capabilities/markdown`, `blesta://capabilities/json`.
  - **Prompts:** `blesta_audit_client`, `blesta_plan_migration`,
    `blesta_reconcile_invoices`, `blesta_extract_customer_snapshot`,
    `blesta_map_to_prime_account`.
- **`blesta-mcp` console script** — starts the MCP server over stdio for use with
  Claude Code, Claude Desktop, and other MCP-compatible AI tools.
- **`mcp` optional extra** — `pip install blesta_sdk[mcp]` installs `mcp>=1.0` (Python
  3.10+ only).
- `BLESTA_AUTH_METHOD` / `BLESTA_ALLOW_HTTP` environment variables respected by the MCP
  server's credential resolver.

### Documentation

- **`CLI_USAGE.md`** — comprehensive CLI reference covering all subcommands, output
  formats (JSON, JSONL, CSV), and env var configuration.
- **`MCP_USAGE.md`** — MCP server reference: installation, client config examples for
  Claude Code and Claude Desktop, full tool/resource/prompt documentation with parameter
  tables, and important constraints for billing mutation safety.
- **README.md** updated with MCP installation option, expanded CLI subcommand section,
  and MCP Server section with tools/resources tables and client config snippet.
- **`SDK_USAGE.md`** updated with canonical sub-package import paths.

### Internal

- Compatibility shims (`blesta_sdk._client`, `_async_client`, `_discovery`, etc.) kept
  as thin re-exports so all existing import paths continue to work without change.
- Patch paths for test mocking preserved: `blesta_sdk._client.time`, `_async_client.asyncio`,
  `_response.json`, `_retry.random` all importable via shims.

## [0.7.0] - 2026-05-27

### Added
- `BlestaEnvConfig` — select credentials for a named deployment environment (`dev`, `stage`, or `live`) from environment variables (`BLESTA_{ENV}_URL/USER/KEY`) or constructor kwargs. `client()` returns a ready-to-use `BlestaRequest`. Requires `blesta_sdk[cli]` for `.env` file loading.
- `_redaction.py` shared module — `redact_args()` extracted from `_client.py` into a dedicated module shared by both sync and async clients; eliminates cross-module import and keeps redaction logic in one place.

### Changed
- **Retry semantics clarified (breaking for any code relying on POST/PUT 5xx retry):** POST and PUT requests are never retried on 5xx responses, even when `retry_mutations=True`. A 5xx does not guarantee the write failed — retrying risks duplicate billing records. `retry_mutations=True` now enables retry on 429 (rate-limit) only for mutations. GET and DELETE continue to retry on both 5xx and 429.
- `allow_http=True` is now required to use an `http://` base URL. Passing an HTTP URL without this flag raises `ValueError`. This protects credentials from being sent in plaintext by accident. **Breaking change** for any code using `http://` URLs without the flag.
- **`generate_capabilities_report(format=...)` renamed to `output_format=`** (breaking for callers using the keyword argument). The old `format` name shadowed the Python built-in; any caller must rename the kwarg to `output_format=`.

### Fixed
- Response correctness: Blesta returns HTTP 200 with an `errors` key for validation failures (e.g., duplicate client). `BlestaResponse.errors()` now correctly surfaces these payloads. Previously, callers checking only `status_code == 200` could miss validation errors.
- Pagination integrity: falsy scalar payloads (e.g., `0`, `false`) returned by `getListCount`-style methods no longer trigger a premature stop. Stuck-page detection now distinguishes an empty list response from a legitimate scalar.
- Discovery runtime safety: `BlestaDiscovery` no longer uses bare `assert` statements for internal validation. All assertions replaced with `ValueError` / `RuntimeError` raises so errors surface cleanly in production (Python's `-O` flag strips asserts).
- Async concurrency: `AsyncBlestaRequest.extract()` and `get_all_fast()` now gate all concurrent requests through the client-level semaphore (`max_concurrency`, default 10), preventing request storms when processing large target lists.
- CLI redaction: `get_last_request()` redacts sensitive keys from `args` before returning. Previously, raw API key values could appear in debug/log output via `--last-request`.
- Schema tooling: `extract_schema.py` and `extract_plugin_schema.py` now write to `src/blesta_sdk/schemas/` (the canonical bundled location) instead of the deprecated root `schemas/` directory.

### Documentation
- README rewritten with repo identity ("what it is / what it does not do"), use-cases section (good fits and risky uses), sync-vs-async guidance, `allow_http` examples, HTTP 200 body-error warnings, redaction section, and migration-safety section.
- `SDK_USAGE.md` updated with HTTP 200 body-error note and redaction documentation.
- `BlestaEnvConfig` now documented in both README and SDK_USAGE with env-var table, isolation behavior, and client usage examples.
- `raise_for_status()` / `raise_on_error=True` now documented to cover HTTP 200 body errors, not only HTTP error status codes.
- Pagination section clarifies `iter_all` vs `get_all` trade-offs and stuck-page protection.
- CLI `--last-request` output noted as redacted.

### Internal
- Migration docs: `docs/` now includes idempotency design guidance for billing writes — ledger dedup and check-before-create patterns for safe retry in the face of server errors.

## [0.6.0] - 2026-03-02

### Added
- `raise_for_status()` method on `BlestaResponse` — raises typed exceptions for non-success responses. No-op for 1xx–3xx status codes.
- `raise_on_error` flag on `BlestaRequest` and `AsyncBlestaRequest` (default `False`). When `True`, `submit()` calls `raise_for_status()` before returning.
- Exception hierarchy: `BlestaError` (base), `BlestaConnectionError` (status 0), `BlestaAPIError` (4xx), `BlestaAuthError` (401/403), `BlestaRateLimitError` (429, includes `retry_after`), `BlestaServerError` (5xx). All carry `status_code`, `errors`, and `headers`.
- `response.headers` property on `BlestaResponse` — exposes HTTP response headers as `Mapping[str, str]`.
- Automatic 429 retry with `Retry-After` support. When a 429 response includes a `Retry-After` header (seconds), the client sleeps for that duration instead of exponential backoff. Falls back to backoff if the header is absent or unparseable. Respects `max_retries` and `retry_mutations` gating.
