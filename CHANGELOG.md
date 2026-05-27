# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
