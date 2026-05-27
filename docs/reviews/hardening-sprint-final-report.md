# Blesta SDK Hardening Sprint — Final Report

**Date:** 2026-05-27  
**Author:** jwogrady  
**Repo:** https://github.com/jwogrady/blesta_sdk  
**Review range:** `5fa6262..c7faadf`  
**Base (pre-sprint):** `5fa6262` — docs: add 2026-05-27 code review (16 findings, 8 test gaps)  
**Head (post-sprint):** `c7faadf` — merge: hardening sprint complete (lanes 1-11, #8–#14, #16–#23, #32–#33)

---

## Test Results

| Command | Result |
|---------|--------|
| `uv run pytest -q -m "not integration"` | **730 passed**, 1 deselected (integration), 0 failures |
| `uv run pytest --cov=blesta_sdk --cov-fail-under=97` | **97.04%** — threshold met |
| `uv run black --check src/ tests/ tools/` | ✅ 25 files unchanged |
| `uv run ruff check src/ tests/ tools/` | ✅ All checks passed |

---

## Issues Addressed

### Lane 1 — Response correctness

**#8 [HIGH]** HTTP 200 validation failures invisible  
**#24 [TEST]** Missing: HTTP 200 with `{"errors":{}}` body treated as success

- `BlestaResponse.errors()` now detects Blesta's plural `"errors"` key in HTTP 200 bodies.
- `raise_for_status()` raises `BlestaAPIError` when HTTP 200 carries validation errors.
- Commit: `9369168`

---

### Lane 2 — Pagination integrity

**#10 [HIGH]** Falsy-zero terminates pagination early  
**#17 [MEDIUM]** Alternating bad pages escape stuck-page detector

- `PaginationState.check_data()` changed from `if not data` to
  `if data is None or data == [] or data == {}` — preserves `0`, `False`, `""`.
- Added a 6-slot rolling window of page-content hashes; raises `PaginationError`
  when the window contains exactly 2 unique hashes in alternating order (A→B→A→B).
- Commit: `5097a5a`

---

### Lane 3 — HTTP + path validation hardening

**#11 [HIGH]** Credentials sent over plaintext HTTP with no warning  
**#16 [MEDIUM]** `validate_segment()` doesn't block percent-encoded path traversal

- Both `BlestaRequest` and `AsyncBlestaRequest` raise `ValueError` on `http://` URLs
  unless `allow_http=True` is passed explicitly to the constructor.
- `validate_segment()` now rejects any segment containing `%`, blocking `%2F`,
  `%2e%2e`, `%00`, and all other percent-encoded bypasses.
- Commit: `b561201`

---

### Lane 4 — Retry semantics / billing safety

**#12 [HIGH]** `retry_mutations=True` can duplicate billing writes on 5xx

- POST and PUT requests now only retry on HTTP 429 (rate-limit), never on 5xx.
- A server error does not guarantee the write failed; retrying risks duplicate records.
- GET/DELETE continue to retry on both 5xx and 429.
- Commit: `37e012a`

---

### Lane 5 — Discovery runtime safety

**#9 [HIGH]** `assert` guards in `BlestaDiscovery` silently removed under `python -O`

- All 14 `assert` statements in `_discovery.py` replaced with explicit
  `if ... raise RuntimeError(...)` checks that survive the optimizer.
- Commit: `bb5f5d7`

---

### Lane 6 — Async concurrency

**#13 [MEDIUM]** `get_all_fast` fallback to `get_all` bypasses semaphore  
**#15 [MEDIUM]** `extract` holds semaphore for entire multi-page fetch

- `get_all_fast()` fallback path now wrapped in `async with self._semaphore:`.
- `extract()` gates each individual page request inside the semaphore via an
  inline pagination loop (one acquire/release per request, not per model).
- Commit: `5bc10f7`

---

### Lane 7 — CLI last_request redaction

**#19 [MEDIUM]** `_last_request` stores args by mutable reference — CLI prints sensitive params

- `submit()` now stores `args.copy()` in `_last_request`, preventing mutation of
  the stored record after the call.
- `get_last_request()` returns a redacted view via `_redact_args()`, replacing the
  values of sensitive keys with `"***"`.
- Redacted keys (case-insensitive): `api_key`, `password`, `pass`, `secret`,
  `token`, `auth`, `authorization`, `card_number`, `cvv`, `cvc`, `ssn`,
  `bank_account`, `routing_number`.
- Commit: `5bc10f7`

---

### Lane 8 — API semantics cleanup

**#18 [MEDIUM]** `call_all()` claims schema inference but unconditionally calls `get_all()`  
**#20 [MEDIUM]** `call()` silently falls back to POST for unknown methods  
**#21 [LOW]** `count_for()` fallback fires unvalidated `list_method+Count` endpoint  
**#22 [LOW]** `format` parameter in `generate_capabilities_report` shadows built-in  
**#23 [LOW]** `BlestaDiscovery` global singleton ignores custom schema paths from caller

- `call()` raises `ValueError` when neither schema nor prefix heuristics resolve the method.
- `call_all()` looks up the method in the schema and raises `ValueError` if it resolves
  to a non-GET verb before paginating.
- `count_for()` emits `logger.warning()` when falling back to `list_method + "Count"`.
- `generate_capabilities_report()` parameter renamed `format` → `output_format`.
- Both clients accept `discovery=` constructor argument; `_get_discovery()` returns
  the injected instance directly, bypassing the module singleton.
- Commit: `5bc10f7` / `bb5f5d7`

---

### Lane 7–8 Test Gaps (issues #25–#31)

**#25** Non-integer Retry-After (float / HTTP-date) — `test_retry_after_float_header`, `test_retry_after_http_date_header`  
**#26** `iter_all` `on_error=raise` with page-1 failure — `test_iter_all_on_error_raise_page1_failure`  
**#27** SSL error path — `test_ssl_error_returns_blesta_response`  
**#28** Async header auth `client.auth is None` — `test_async_header_auth_sets_auth_none`  
**#29** `to_dataframe()` after `free_raw()` — `test_to_dataframe_after_free_raw`  
**#30** Successful first POST must not retry — `test_retry_mutations_successful_first_post_returns_immediately`  
**#31** `get_all_fast(verify=True)` count mismatch — `test_get_all_fast_verify_count_mismatch_logs_warning`

All committed in: `5bc10f7`

---

### Lane 9 — Schema refresh workflow

**#32 [MEDIUM]** No automated schema refresh in CI

- Added `.github/workflows/schema-refresh.yml`: weekly Monday 06:00 UTC +
  `workflow_dispatch` trigger.
- Runs both `extract_schema.py` and `extract_plugin_schema.py`.
- Opens a PR via `peter-evans/create-pull-request@v6` when any schema file changes.
- Updated `DEFAULT_OUTPUT` in both tools to write to `src/blesta_sdk/schemas/`
  (the canonical bundled location) rather than the deprecated root `schemas/`.
- Commit: `6aa69a6`

---

### Lane 10 — Migration idempotency design

**#33 [MEDIUM]** No idempotency mechanism for billing POST mutations

- Added `docs/migration.md` documenting the ledger + check-then-create + source-ID
  pattern for safe, restartable migrations.
- Covers entity migration order: clients → contacts → services → invoices →
  transactions → payment accounts.
- Explicitly states `retry_mutations=True` **must not** be used as an idempotency
  mechanism (it only retries 429s, does not prevent duplicate writes on 5xx).
- Commit: `1973891`

---

### Lane 11 — Dev/stage/live environment config

**#14** Add support for dev, stage, and live environment configuration

- Added `BlestaEnvConfig` (exported from `blesta_sdk.__all__`).
- Accepts `env="dev"|"stage"|"live"` and resolves credentials from:
  1. Explicit constructor kwargs (`url=`, `user=`, `key=`)
  2. Environment variables `BLESTA_{ENV}_URL`, `BLESTA_{ENV}_USER`, `BLESTA_{ENV}_KEY`
- Never falls back between environments (stage credentials are never used for live).
- `cfg.client(**kwargs)` returns a configured `BlestaRequest`.
- Added `.env.example` with placeholder-only values.
- 17 tests in `tests/test_env_config.py`.
- Commits: `2d4ad44`, `8315a49`

---

## Breaking Changes

1. **`call()` raises `ValueError`** for methods that cannot be resolved to an HTTP verb.
   Previously silently fell back to POST. Callers that relied on the fallback must either
   pass `action=` explicitly or use schema-resolvable method names.

2. **`http://` URLs raise `ValueError`** by default in both sync and async clients.
   Existing `BlestaRequest("http://...")` calls must add `allow_http=True` to opt in.

3. **POST/PUT no longer retry on 5xx** even when `retry_mutations=True`.
   Only HTTP 429 triggers a retry for mutations. This is intentional and correct — a
   5xx does not guarantee the write failed.

4. **`generate_capabilities_report(format=...)` → `output_format=`**.
   Any caller using the keyword argument `format=` must rename it `output_format=`.

---

## Known Risks / Deferred Items

- **`_discovery.py` RuntimeError guards (13 lines, 93% branch coverage)**: The guards
  protecting against `_registry is None` after `_ensure_loaded()` are practical
  dead code in normal operation. Tests exist for the primary paths; triggering these
  specific guards requires direct object manipulation. Left as-is; they are defensive
  checks, not behavior paths.

- **`__init__.py` ImportError path for `AsyncBlestaRequest` (lines 39–40)**: Triggered
  only when `httpx` is not installed. Not covered in CI (httpx is always present in the
  dev environment). Acceptable coverage gap.

- **`_pagination.py` hash-exception path (lines 122–123)**: Triggered only when
  `hash(str(data))` raises, which is not possible with standard Python types. Defensive
  code; left uncovered.

- **`_response.py` line 240** (`CSV + non-200`): `is_csv` returns `False` for non-200
  responses, making the inner `status_code != 200` branch in `errors()` unreachable
  through normal construction. Logically dead; acceptable.

- **Schema refresh CI** (#32): The `peter-evans/create-pull-request@v6` action requires
  a valid `GITHUB_TOKEN` or PAT with PR write permission. Has not been exercised against
  the live repo yet.

---

## Commit Range

```
5fa6262..c7faadf
```

```
5fa6262  docs: add 2026-05-27 code review (16 findings, 8 test gaps)   ← BASE (pre-sprint)
875e82a  fix(response): surface Blesta 200 validation errors (#8, #24)
f77af7d  fix(pagination): preserve falsy scalar payloads, detect alternating loops (#10, #17)
9369168  fix(response): surface Blesta 200 validation errors (#8, #24)  [merge]
5097a5a  fix(pagination): preserve falsy scalar payloads, detect alternating loops (#10, #17)
b561201  fix(client): require explicit HTTP opt-in, block percent-encoded paths (#11, #16)
37e012a  fix(client): don't retry mutations on 5xx, only 429 (#12)
bb5f5d7  fix(discovery): replace assert guards with RuntimeError, rename format param (#9, #22, #23)
fd97f31  merge: lanes 3-5 + API semantics cleanup (#9, #11, #12, #16, #22, #23)  [merge]
5bc10f7  fix(client): API semantics, last_request redaction/copy, async semaphore (#13, #15, #18, #19, #20, #21)
6aa69a6  fix(schemas): point extraction tools at canonical path, add weekly refresh CI workflow (#32)
1973891  docs(migration): add idempotency design — ledger + check-then-create + source IDs (#33)
2d4ad44  feat(config): add BlestaEnvConfig for dev/stage/live environment selection (#14)
8315a49  tests: add coverage gap tests, mark unreachable retry return pragma no cover
c7faadf  merge: hardening sprint complete (lanes 1-11, #8–#14, #16–#23, #32–#33)  ← HEAD
```

---

## Files Changed (summary)

| File | Change |
|------|--------|
| `src/blesta_sdk/_response.py` | Detect plural `errors` key; `raise_for_status` on 200+errors |
| `src/blesta_sdk/_pagination.py` | Falsy-zero fix; alternating-page window detection |
| `src/blesta_sdk/_validation.py` | Block `%`-encoded segments |
| `src/blesta_sdk/_client.py` | `allow_http`, percent-encoding, mutation retry, `call()`/`call_all()`/`count_for()` semantics, `_last_request` redaction, injectable `discovery=` |
| `src/blesta_sdk/_async_client.py` | Mirror of sync client fixes; semaphore gating for `get_all_fast` and `extract` |
| `src/blesta_sdk/_discovery.py` | Replace `assert` → `RuntimeError`; rename `format` → `output_format` |
| `src/blesta_sdk/_env_config.py` | **New**: `BlestaEnvConfig` |
| `src/blesta_sdk/__init__.py` | Export `BlestaEnvConfig` |
| `.env.example` | **New**: placeholder-only credentials template |
| `.github/workflows/schema-refresh.yml` | **New**: weekly schema refresh CI |
| `docs/migration.md` | **New**: migration idempotency design |
| `docs/reviews/hardening-sprint-final-report.md` | **New**: this file |
| `CLAUDE.md` | Note canonical schema location |
| `tools/extract_schema.py` | Write to `src/blesta_sdk/schemas/` |
| `tools/extract_plugin_schema.py` | Write to `src/blesta_sdk/schemas/` |
| `tests/test_blesta_sdk.py` | +~280 lines of new/updated tests |
| `tests/test_async_client.py` | +~103 lines of new tests |
| `tests/test_env_config.py` | **New**: 17 tests for `BlestaEnvConfig` |
