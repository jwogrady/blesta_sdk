# Code Quality Audit

**Date:** 2026-05-27  
**Version audited:** 0.8.1  
**Branch:** `chore/code-quality-inventory`

---

## Summary

The `blesta_sdk` codebase is in good shape overall. The architecture is clean, tests are comprehensive (929 passing, 97%+ coverage enforced), lint and formatting checks pass, and the package builds successfully. The main areas of concern are:

1. **Credential/client construction logic is duplicated across 6 locations** (CLI commands, legacy CLI module, and MCP schemas helper). The MCP surface already consolidates this into `_build_client()`; the CLI surface has not followed suit.
2. **`_cli.py` is a legacy full implementation** that is no longer the active entry point but remains tested directly with 20+ unit tests. It contains duplicate logic relative to `cli/app.py`'s `_run_legacy()`.
3. **The `_run_legacy()` docstring is incorrect** — it claims to delegate to `blesta_sdk._cli.cli` but contains a standalone reimplementation.
4. **`BLESTA_ALLOW_HTTP` is missing from the CLI env vars table** in `CLI_USAGE.md`.
5. **11 compatibility shims** (`_client.py`, `_async_client.py`, etc.) are all active — they serve external import compatibility AND are required by tests that patch via the old module paths. None can be removed without migrating the tests.

No outright dead code was found. All identified candidates are either externally reachable (public API surface), required by tests, or intentional compatibility shims with documented purposes.

---

## Package / File Map

```
src/blesta_sdk/
├── __init__.py                  # Top-level exports + lazy AsyncBlestaRequest loader
│
├── _*.py (11 files)             # Backward-compat shims → re-export from core/ or discovery/
│   ├── _client.py               # → core/client; re-exposes `time` for test patches
│   ├── _async_client.py         # → core/async_client; re-exposes `asyncio` + ContextVar
│   ├── _cli.py                  # Legacy CLI implementation (FULL, not just a shim)
│   ├── _dateutil.py             # → core/dateutil
│   ├── _discovery.py            # → discovery/registry
│   ├── _env_config.py           # → core/config
│   ├── _exceptions.py           # → core/errors
│   ├── _pagination.py           # → core/pagination
│   ├── _redaction.py            # → core/redaction
│   ├── _retry.py                # → core/retry; re-exposes `random` for test patches
│   └── _validation.py           # → core/validation
│
├── core/                        # Canonical SDK implementation (11 modules)
│   ├── client.py                # BlestaRequest sync client (727 lines)
│   ├── async_client.py          # AsyncBlestaRequest async client (960 lines)
│   ├── config.py                # BlestaEnvConfig (130 lines)
│   ├── errors.py                # Exception hierarchy (99 lines)
│   ├── response.py              # BlestaResponse (301 lines)
│   ├── pagination.py            # PaginationState (187 lines)
│   ├── redaction.py             # redact_args() (121 lines)
│   ├── retry.py                 # jitter_delay() (19 lines)
│   ├── validation.py            # validate_segment() (41 lines)
│   ├── dateutil.py              # _month_boundaries() (43 lines)
│   └── __init__.py              # Core exports (29 lines)
│
├── discovery/                   # Schema-driven API introspection
│   ├── registry.py              # BlestaDiscovery, MethodSpec (449 lines)
│   └── __init__.py
│
├── cli/                         # CLI adapter (thin)
│   ├── app.py                   # main(), _build_parser(), _run_legacy() (195 lines)
│   ├── formatters.py            # print_json(), print_error() (61 lines)
│   ├── __init__.py
│   └── commands/
│       ├── call.py              # `blesta call` subcommand (98 lines)
│       ├── discover.py          # `blesta discover` subcommand (81 lines)
│       ├── extract.py           # `blesta extract` subcommand (111 lines)
│       ├── report.py            # `blesta report` subcommand (103 lines)
│       └── __init__.py
│
├── mcp/                         # MCP adapter (thin)
│   ├── server.py                # _build_server(), main() (102 lines)
│   ├── tools.py                 # 10 tool handlers + TOOL_REGISTRY (323 lines)
│   ├── resources.py             # 7 resource handlers + registries (187 lines)
│   ├── prompts.py               # 5 prompt templates + PROMPT_REGISTRY (145 lines)
│   ├── schemas.py               # _creds_from_env(), _build_client() (56 lines)
│   └── __init__.py
│
└── schemas/                     # Bundled JSON schemas (package data)
    ├── blesta_api_schema.json   # 63 models (1.3 MB)
    ├── blesta_plugin_schema.json # 8 models (120 KB)
    └── __init__.py

tests/ (13 files)
  conftest.py, test_async_client.py, test_blesta_sdk.py, test_classify.py,
  test_cli_commands.py, test_discovery.py, test_env_config.py, test_mcp.py,
  test_plugin_schema.py, test_redaction.py, test_response_edge_cases.py,
  test_retry.py, test_schema.py

tools/ (4 files)
  extract_schema.py, extract_plugin_schema.py, _classify.py, __init__.py
```

---

## Public API Map

### Top-level (`blesta_sdk`)

| Name | Type | Source |
|---|---|---|
| `BlestaRequest` | class | `blesta_sdk.core.client` |
| `AsyncBlestaRequest` | class (lazy) | `blesta_sdk.core.async_client` |
| `BlestaEnvConfig` | class | `blesta_sdk.core.config` |
| `BlestaResponse` | class | `blesta_sdk.core.response` |
| `BlestaDiscovery` | class | `blesta_sdk.discovery.registry` |
| `MethodSpec` | class | `blesta_sdk.discovery.registry` |
| `BlestaError` | exception | `blesta_sdk.core.errors` |
| `BlestaAPIError` | exception | `blesta_sdk.core.errors` |
| `BlestaAuthError` | exception | `blesta_sdk.core.errors` |
| `BlestaRateLimitError` | exception | `blesta_sdk.core.errors` |
| `BlestaServerError` | exception | `blesta_sdk.core.errors` |
| `BlestaConnectionError` | exception | `blesta_sdk.core.errors` |
| `PaginationError` | exception | `blesta_sdk.core.errors` |
| `__version__` | str (dynamic) | `importlib.metadata` |

### Canonical submodule paths (also stable public API)

- `blesta_sdk.core.client.BlestaRequest`
- `blesta_sdk.core.async_client.AsyncBlestaRequest`
- `blesta_sdk.core.config.BlestaEnvConfig`
- `blesta_sdk.core.response.BlestaResponse`
- `blesta_sdk.core.errors.*`
- `blesta_sdk.discovery.registry.BlestaDiscovery`
- `blesta_sdk.discovery.registry.MethodSpec`

### Backward-compat shim paths (kept for external users, do not remove)

- `blesta_sdk._client.BlestaRequest`
- `blesta_sdk._async_client.AsyncBlestaRequest`
- `blesta_sdk._env_config.BlestaEnvConfig`
- `blesta_sdk._response.BlestaResponse`
- `blesta_sdk._exceptions.*`
- `blesta_sdk._discovery.BlestaDiscovery`
- `blesta_sdk._pagination.PaginationState`
- `blesta_sdk._redaction.redact_args`
- `blesta_sdk._retry.jitter_delay`
- `blesta_sdk._validation.validate_segment`
- `blesta_sdk._dateutil._month_boundaries`

---

## CLI Entry Point Map

| Command | Entry point | File |
|---|---|---|
| `blesta` | `blesta_sdk.cli.app:main` | `cli/app.py` |
| `blesta call` | `cli/commands/call.py:run()` | via `app.py` subparser |
| `blesta extract` | `cli/commands/extract.py:run()` | via `app.py` subparser |
| `blesta report` | `cli/commands/report.py:run()` | via `app.py` subparser |
| `blesta discover` | `cli/commands/discover.py:run()` | via `app.py` subparser |
| `blesta --model X --method Y` | `cli/app.py:_run_legacy()` | legacy compat mode |

Legacy entry point (no longer wired as a script, but still accessible):
- `blesta_sdk._cli:cli()` — original flat-flag CLI; not invoked by `blesta` script

---

## MCP Tool / Resource / Prompt Map

### Tools (10)

| Tool name | Handler |
|---|---|
| `blesta_call` | `_call_handler` |
| `blesta_get_all` | `_get_all_handler` |
| `blesta_extract` | `_extract_handler` |
| `blesta_count` | `_count_handler` |
| `blesta_get_report` | `_get_report_handler` |
| `blesta_get_report_series` | `_get_report_series_handler` |
| `blesta_list_models` | `_list_models_handler` |
| `blesta_list_methods` | `_list_methods_handler` |
| `blesta_get_method_spec` | `_get_method_spec_handler` |
| `blesta_capabilities_report` | `_capabilities_report_handler` |

### Resources (7)

| URI | Handler |
|---|---|
| `blesta://schema/core` | `_schema_core_handler` |
| `blesta://schema/plugin` | `_schema_plugin_handler` |
| `blesta://models` | `_models_handler` |
| `blesta://capabilities/markdown` | `_capabilities_markdown_handler` |
| `blesta://capabilities/json` | `_capabilities_json_handler` |
| `blesta://models/{model}` | `_model_handler` |
| `blesta://models/{model}/methods/{method}` | `_method_handler` |

### Prompts (5)

| Prompt name | Description |
|---|---|
| `blesta_audit_client` | Audit a Blesta client account |
| `blesta_plan_migration` | Plan a Blesta data migration |
| `blesta_reconcile_invoices` | Reconcile invoices against payment transaction records |
| `blesta_extract_customer_snapshot` | Extract a full customer snapshot |
| `blesta_map_to_prime_account` | Map Blesta fields to a target billing system schema |

---

## Duplicate Code Candidates

### HIGH priority: Credential resolution and client construction (6 locations)

The same pattern — read `BLESTA_API_URL` / `BLESTA_API_USER` / `BLESTA_API_KEY` / `BLESTA_AUTH_METHOD` / `BLESTA_ALLOW_HTTP` from env, then construct a `BlestaRequest` — appears in:

1. `src/blesta_sdk/_cli.py` — `cli()` function (legacy, inline)
2. `src/blesta_sdk/cli/app.py` — `_run_legacy()` (inline)
3. `src/blesta_sdk/cli/commands/call.py` — `run()` (inline)
4. `src/blesta_sdk/cli/commands/extract.py` — `run()` (inline)
5. `src/blesta_sdk/cli/commands/report.py` — `run()` (inline)
6. `src/blesta_sdk/mcp/schemas.py` — `_creds_from_env()` + `_build_client()` (consolidated)

The MCP surface correctly centralised this into `mcp/schemas._build_client()`. The CLI surface should follow: a `cli/client.py` (or `cli/app.py`-level helper) mirroring `_build_client()` would eliminate the 5-way duplication across the CLI modules.

### LOW priority: `allow_http` truthy parsing (3 locations)

The set `{"1", "true", "yes", "on"}` appears inline in `cli/app.py`, `mcp/schemas.py`, and is abstracted into `_env_truthy()` only in the legacy `_cli.py`. A shared `_env_truthy()` in `cli/app.py` (or a common `cli` helper) would remove the inline set repetition.

---

## Dead Code Candidates

### CONFIRMED NOT DEAD — do not remove

| Path | Why it is still alive |
|---|---|
| `src/blesta_sdk/_cli.py` | Imported directly by 20+ tests; legacy users may import `blesta_sdk._cli:cli` |
| All `_*.py` shims | External import compat + test patch infrastructure (e.g. `patch("blesta_sdk._client.time.sleep")`) |
| `cli/app.py:_run_legacy()` | Handles `blesta --model X --method Y` invocations in production |

### POSSIBLE dead code — verify before acting

| Path | Notes |
|---|---|
| `_cli.py:_env_truthy()` | Private helper only used inside `_cli.py`; not exported anywhere |
| `_discovery.py` re-exports of internal names (`_DELETE_PREFIXES`, etc.) | Exposes private names at shim path; external users should not rely on these |

No outright dead code was found that can be safely removed without further investigation.

---

## Unnecessary Nesting Candidates

None found. The four-tier layout (`core/`, `discovery/`, `cli/`, `mcp/`) is appropriate and well-balanced. The `cli/commands/` subdirectory is shallow (one level) and provides a clean extension point.

The `_*.py` shim files add apparent noise at the root package level but are functionally necessary and are self-documenting (each has a one-line module docstring identifying it as a compatibility shim).

---

## Docs / Code Mismatch List

| Severity | Location | Issue |
|---|---|---|
| **MEDIUM** | `src/blesta_sdk/cli/app.py:118` | `_run_legacy` docstring says "Delegates to the original `blesta_sdk._cli.cli` implementation" — this is incorrect. The function contains a standalone reimplementation; it does not call `_cli.cli()`. |
| **LOW** | `CLI_USAGE.md`, env vars table (lines 199–202) | `BLESTA_ALLOW_HTTP` env var is missing. It is documented in `MCP_USAGE.md` and referenced in `README.md` and the source, but not listed in the CLI env vars reference table. |
| **INFO** | `MCP_USAGE.md:341` | Prompt table shows 5 of 5 prompts correctly; no mismatch. |
| **INFO** | `MCP_USAGE.md:325–331` | Resource URIs match code registrations exactly; no mismatch. |
| **INFO** | `MCP_USAGE.md:93–303` | All 10 tool names match `TOOL_REGISTRY` exactly; no mismatch. |
| **INFO** | `README.md` / `SDK_USAGE.md` / `CLI_USAGE.md` | Install commands match `pyproject.toml` extras (`cli`, `async`, `mcp`, `data`). |
| **INFO** | `CLAUDE.md` | Notes deprecated root-level `schemas/` dir, but that directory does not exist in the working tree. The note is pre-emptive, not stale. |

---

## Risk Ranking

| Risk | Issue | Recommended action |
|---|---|---|
| **Docs accuracy** (low blast radius) | `_run_legacy` docstring is wrong | Fix docstring in Issue #88 (docs drift PR) |
| **Docs gap** (low blast radius) | `BLESTA_ALLOW_HTTP` missing from `CLI_USAGE.md` | Add to env vars table in Issue #88 |
| **Maintenance burden** (medium blast radius) | Credential resolution duplicated 5× in CLI | Consolidate in Issue #86 (dedup PR) |
| **Test patch fragility** (low blast radius) | Tests patch via `_*.py` shim paths | No action needed unless shims are removed (they shouldn't be) |
| **Legacy CLI confusion** (low blast radius) | `_cli.py` has duplicate logic vs `_run_legacy()` | Document relationship; do not remove `_cli.py` yet — requires test migration |

---

## Recommended PR Sequence

| # | Issue | Branch | Scope | Risk |
|---|---|---|---|---|
| 1 | #84 (this) | `chore/code-quality-inventory` | Audit document only | None |
| 2 | #85 | `refactor/remove-dead-code` | No confirmed dead code found — close with "nothing to remove" note | None |
| 3 | #86 | `refactor/deduplicate-shared-logic` | Extract `_build_cli_client()` helper in CLI, eliminating 4×-duplicate cred resolution | Low |
| 4 | #87 | `refactor/simplify-module-boundaries` | No structural changes needed — nesting is appropriate | None |
| 5 | #88 | `docs/verify-code-docs-match` | Fix `_run_legacy` docstring + add `BLESTA_ALLOW_HTTP` to CLI_USAGE.md | None |
| 6 | #89 | `chore/code-quality-final-qa` | Full validation pass + CHANGELOG update | None |

---

## Checks Run for This Audit

```
uv sync                                            OK
uv run pytest -v -m "not integration"              929 passed, 1 deselected
uv run ruff check src/ tests/ tools/               All checks passed
uv run black --check src/ tests/ tools/            58 files unchanged
uv build                                           dist/blesta_sdk-0.8.1.tar.gz + .whl built
uvx twine check dist/*                             PASSED (all 8 dist files)
uv run python -m compileall src                    OK (no errors)
```

Static type checkers (mypy, pyright) and dead-code finder (vulture) are not configured in the project. No new dev dependencies were added.
