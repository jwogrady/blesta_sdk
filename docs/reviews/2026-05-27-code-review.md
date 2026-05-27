# Code Review — blesta_sdk
**Date:** 2026-05-27  
**Scope:** Full repository (v0.6.0)  
**Method:** 5-lane parallel review (correctness, security, architecture, tests, language pitfalls)  
**Verdict:** needs major fixes

---

## Executive Summary

The package is well-structured and impressively far along for a v0.6.0 SDK. The pagination engine, async client, exception hierarchy, and discovery layer are all thoughtful. However, there are **two correctness bugs that will silently produce wrong results in production**, **one critical security finding**, and **several billing-safety gaps** that matter given the intended use in a real billing ecosystem. These need to be addressed before this package is trusted with payment or invoice mutations.

---

## Top 5 Risks

| Rank | Severity | Finding | Files | Impact |
|------|----------|---------|-------|--------|
| 1 | **Critical** | Live API credentials in `.env` at repo root | `.env` | One `git add -A` slip publishes real API keys |
| 2 | **High** | `if not data` in pagination stops on valid `0`/`False` responses | `_pagination.py:81` | Silent data loss — whole pages dropped, caller never knows |
| 3 | **High** | `errors()` returns `None` for HTTP 200 with `{"errors": {...}}` body | `_response.py:218-234` | Blesta validation failures treated as success; billing mutations appear to succeed when they fail |
| 4 | **High** | `assert` guards in `BlestaDiscovery` disappear under `python -O` | `_discovery.py` (14 sites) | All discovery calls raise opaque `AttributeError` instead of useful error when schemas fail to load |
| 5 | **High** | `retry_mutations=True` retries 5xx blindly after a potential successful write | `_client.py:209-270` | If Blesta wrote the invoice/payment but failed to respond, the retry creates a duplicate |

---

## Detailed Findings

### F-01 — BLOCKER: Live credentials in `.env`

**File:** `.env` (repo root)  
**Issue:** `BLESTA_API_KEY` and `NAMESILO_KEY` present in plaintext. File is in `.gitignore` but exists on disk.  
**Why it matters:** Any `git add -A`, IDE auto-stage, or `git stash` interaction could commit both keys. NAMESILO credentials are from a different project entirely.  
**Fix:** Delete `.env` now. Rotate both keys. Add `.env.example` with placeholder values only.

---

### F-02 — HIGH: Falsy-zero terminates pagination early

**File:** `src/blesta_sdk/_pagination.py:81`  
**Code:** `if not data: return True`  
**Issue:** Treats `0`, `False`, `""`, and `{}` as empty pages and stops iteration.  
**Failure scenario:** Endpoint returns `{"response": 0}` — `not 0 == True`, iterator stops, page silently dropped.  
**Fix:**
```python
# Before
if not data: return True
# After
if data is None or data == [] or data == {}: return True
```

---

### F-03 — HIGH: HTTP 200 validation failures are invisible

**File:** `src/blesta_sdk/_response.py:218-234`  
**Issue:** Blesta returns validation errors as HTTP 200 with body `{"errors": {"field": "message"}}`. The `errors()` method for 200 responses checks only for the singular `"error"` key (the SDK's own internal error format), never the plural `"errors"` key that Blesta actually returns. Result: `response.errors()` returns `None`, `raise_on_error=True` does not raise.

Additionally: malformed-but-200 responses store `{"error": "Invalid JSON..."}` — `data` returns `None`, `errors()` returns `None`, failure is invisible.  
**Failure scenario:** `api.post("clients", "create", {...invalid fields...})` → HTTP 200 with `{"errors": {"email": "Invalid"}}` → caller believes client was created.  
**Fix:**
```python
if self._status_code == 200:
    errs = formatted.get("errors") or formatted.get("error")
    return errs if errs else None
```

---

### F-04 — HIGH: `assert` guards removed under `python -O`

**File:** `src/blesta_sdk/_discovery.py` — 14 sites (lines 190-192, 228-229, 243, 259-260, 298, 320, 337-338, 390-391)  
**Issue:** All post-`_ensure_loaded()` invariant checks use bare `assert` statements. Under `python -O` or `PYTHONOPTIMIZE=1` (common in production Docker images), these are compiled away entirely.  
**Failure scenario:** Both schema files fail to parse → `_registry` stays `None` → `assert` is gone → `self._registry.get(model)` raises `AttributeError: 'NoneType' object has no attribute 'get'` with no diagnostic context.  
**Fix:** Replace with `if self._X is None: raise RuntimeError("BlestaDiscovery schema failed to load")`, or initialize `_registry = {}` eagerly.

---

### F-05 — HIGH: Credentials sent over plaintext HTTP with no warning

**File:** `src/blesta_sdk/_client.py:95-100`, `src/blesta_sdk/_async_client.py:109-117`  
**Issue:** Both clients mount auth on `"http://"` as well as `"https://"`. No warning or rejection fires if `base_url` starts with `http://`. Basic Auth encodes credentials as base64 — trivially reversible over plaintext.  
**Fix:**
```python
if self.base_url.startswith("http://"):
    logger.warning(
        "base_url uses HTTP — credentials will be sent in plaintext"
    )
```

---

### F-06 — HIGH: `retry_mutations=True` can duplicate billing writes on 5xx

**File:** `src/blesta_sdk/_client.py:209-270`  
**Issue:** When `retry_mutations=True`, a POST that receives a 5xx response is retried. If Blesta wrote the record before the 5xx (e.g., DB write succeeded, response serialization failed), the retry creates a duplicate invoice, payment, or client.  
**Fix:** Narrow `retry_mutations=True` to only retry 429 and network errors for mutations — never 5xx. Document clearly. Consider removing the flag entirely and forcing application-layer retry with duplicate-check logic.

---

### F-07 — MEDIUM: `get_all_fast` fallback to `get_all` bypasses the semaphore

**File:** `src/blesta_sdk/_async_client.py:466-473`  
**Issue:** When `count()` returns 0 or negative, `get_all_fast` falls back to `await self.get_all(...)` without the semaphore. Concurrent callers that all fall back simultaneously issue unbounded page fetches.  
**Failure scenario:** 10 concurrent `get_all_fast` calls all get `count=0` → all fall back → 10 × N pages fire with no rate limiting.  
**Fix:** Wrap the fallback in the semaphore, or apply per-request semaphore gating inside `get_all` itself.

---

### F-08 — MEDIUM: `extract` holds semaphore for entire multi-page fetch

**File:** `src/blesta_sdk/_async_client.py:578-589`  
**Issue:** `_fetch` acquires `self._semaphore` and holds it across the entire `await self.get_all(...)` (N sequential HTTP requests). With `max_concurrency=10` and 10 targets, all 10 grab the semaphore but each serializes its page fetches — effective parallelism collapses.  
**Fix:** Gate per HTTP request, not per model extraction. Move semaphore acquisition inside the page-fetch loop.

---

### F-09 — MEDIUM: Alternating bad pages escape the stuck-page detector

**File:** `src/blesta_sdk/_pagination.py:87-99`  
**Issue:** `_repeat_count` resets to 0 when `data != self._prev_data`. A buggy endpoint alternating between two different bad pages (A→B→A→B...) never triggers the threshold and loops forever (or until `max_pages`).  
**Fix:** Track a rolling window of recent page hashes. Document that `max_pages` is the only hard stop for alternating-page loops.

---

### F-10 — MEDIUM: `validate_segment()` doesn't block percent-encoded path traversal

**File:** `src/blesta_sdk/_validation.py`  
**Issue:** Blocks literal `/` and `..` but not `%2F`, `%2e%2e`, `%00`. These pass through to `requests`/`httpx` and are decoded server-side.  
**Failure scenario:** `model="%2e%2e%2Fconfig"` passes validation, constructing a server-decoded traversal URL.  
**Fix:** `if "%" in segment: raise ValueError(f"{name!r} cannot contain percent-encoded characters")`

---

### F-11 — MEDIUM: `_last_request` stores args by mutable reference; CLI prints sensitive params

**File:** `src/blesta_sdk/_client.py:207-208`, `src/blesta_sdk/_cli.py:97-98`  
**Issue:** `self._last_request = {"url": url, "args": args}` stores the live dict without copying. The CLI `--last-request` flag prints `args` directly to stdout. A `clients/create` call with a `password` field prints the password to the terminal.  
**Fix:** Store `args.copy()`. Redact known sensitive keys before printing in the CLI.

---

### F-12 — MEDIUM: `call_all()` claims schema inference but unconditionally calls `get_all()`

**File:** `src/blesta_sdk/_client.py:628`, `src/blesta_sdk/_async_client.py:829`  
**Issue:** Docstring says "uses schema discovery to confirm the method should be called via GET." Body does `return self.get_all(model, method, args, start_page)` with zero schema consultation.  
**Fix:** Implement the check (`resolve_http_method()` → assert GET) or delete `call_all()`.

---

### F-13 — MEDIUM: `call()` silently falls back to POST for unknown methods

**File:** `src/blesta_sdk/_client.py:589-608`  
**Issue:** When a method is not in the schema and heuristic inference fails, `call()` falls back to POST with only `logger.warning`. In production with WARNING suppressed, a misspelled billing method fires a POST to a nonexistent endpoint silently.  
**Fix:** Raise `ValueError` when both schema and heuristic fail. Callers should not silently send mutations to unknown endpoints.

---

### F-14 — LOW: `count_for()` fallback fires unvalidated endpoint

**File:** `src/blesta_sdk/_client.py:647-651`, `src/blesta_sdk/_async_client.py:849-852`  
**Issue:** Constructs `list_method + "Count"` without schema validation. A nonexistent endpoint returns 0, indistinguishable from "no records."  
**Fix:** Validate the constructed method name exists in the schema before calling, or log a warning when the fallback fires.

---

### F-15 — LOW: `BlestaDiscovery` global singleton ignores custom schema paths

**File:** `src/blesta_sdk/_discovery.py:418-426`, `src/blesta_sdk/_client.py:120-124`  
**Issue:** `_get_discovery()` is `@lru_cache(maxsize=1)` with no arguments — always loads bundled schemas. A user who constructs `BlestaDiscovery(core_schema_path=...)` and then calls `api.call(...)` has their custom schema silently ignored.  
**Fix:** Accept an optional `BlestaDiscovery` instance in the `BlestaRequest` constructor instead of using a module-level singleton.

---

### F-16 — LOW: `format` parameter shadows built-in in `generate_capabilities_report`

**File:** `src/blesta_sdk/_discovery.py:329`  
**Issue:** `def generate_capabilities_report(self, format: Literal["markdown", "json"] = "markdown")` shadows the built-in `format()` function for the method's entire scope.  
**Fix:** Rename to `output_format`. Add ruff `A` rule to catch future builtin shadows.

---

## Critical Test Gaps

| Gap | What could ship undetected |
|-----|---------------------------|
| No test: HTTP 200 with `{"errors": {...}}` body | Validation failures silently treated as success |
| No test: `iter_all` with `on_error="raise"` on page 1 failure | PaginationError regression on first-page failure |
| No test: non-integer `Retry-After` (float/date string) | Server's requested wait ignored; retry storms possible |
| No test: async header auth asserts `client.auth is None` | Double-auth passes silently |
| No test: `retry_mutations=True` with successful first POST | Broken retry condition sends duplicate billing writes |
| No test: SSL error path (`requests.SSLError`) | Narrowing except clause exposes raw exceptions to callers |
| No test: `to_dataframe()` after `free_raw()` | Future refactor silently breaks DataFrame conversion |
| No test: `get_all_fast(verify=True)` count-mismatch path | Verify refactor to raise instead of log is invisible |

---

## Approval Questions

1. Has `.env` been checked against git history? If ever committed and force-pushed, rotate both keys immediately.
2. Is `retry_mutations=True` used in any production callsite today?
3. For the migration use case (status26 → riselocal), what is the plan for idempotency — external IDs, check-then-create, or something else?
4. Are Blesta API calls ever made over plain `http://` in any deployment?
5. Is the bundled schema (`src/blesta_sdk/schemas/`) updated in CI, or only manually?
