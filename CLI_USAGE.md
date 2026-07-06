# CLI Usage Reference

The `blesta` CLI is a thin wrapper around `blesta_sdk.core` for use from the shell. All
business logic lives in the Python SDK — the CLI is a dispatch layer only.

## Installation

```bash
pip install blesta_sdk[cli]   # includes python-dotenv for .env support
# or
uv add "blesta_sdk[cli]"
```

## Credentials

The CLI resolves credentials from environment variables. With the `cli` extra, it also loads
a `.env` file in the current directory at startup:

```env
BLESTA_API_URL=https://your-blesta-domain.com/api
BLESTA_API_USER=your_api_user
BLESTA_API_KEY=your_api_key
```

Optional overrides:

```env
BLESTA_AUTH_METHOD=header    # "basic" (default) or "header"
```

Generate API credentials in Blesta under **Settings > System > API Access**.

---

## Subcommands

### `blesta call`

Invoke a single API method. Infers the HTTP method from the bundled schema; use `--action`
to override.

```
blesta call <model> <method> [--action GET|POST|PUT|DELETE] [--param key=value ...]
```

**Examples:**

```bash
# GET — schema-inferred
blesta call clients getList --param status=active

# Multiple params — pass all pairs after a SINGLE --param flag
blesta call clients getList --param status=active page=1

# POST — explicit action
blesta call clients create --action POST --param firstname=John lastname=Doe

# Schema-aware (HTTP method inferred automatically)
blesta call invoices getList
```

Output is JSON to stdout. On API or HTTP errors, prints a JSON error and exits with code 1.

**Passing multiple params:** `--param` takes all `key=value` pairs after it (e.g.
`--param a=1 b=2`). Repeating the flag (`--param a=1 --param b=2`) keeps only the last
group, so put every pair after one `--param`.

**Value typing:** values are coerced to their natural JSON type — `client_id=868` is sent
as the integer `868`, `flag=true` as a boolean, `ids=[1,2]` as a list. This matters
because Blesta silently ignores numeric filters (like `client_id`) sent as strings.
Values that are not valid JSON stay strings, so plain words (`status=active`), dates, and
leading-zero identifiers (`code=007`) are preserved as-is.

---

### `blesta extract`

Paginate a list endpoint and collect all records across all pages. Equivalent to
`BlestaRequest.get_all()`.

```
blesta extract <model> <method> [--param key=value ...] [--format json|jsonl|csv]
```

**Formats:**

| Format | Description |
|--------|-------------|
| `json` | Pretty-printed JSON array (default) |
| `jsonl` | One JSON object per line — suitable for streaming / large datasets |
| `csv` | CSV with header row — only works when all records have the same keys |

**Examples:**

```bash
# All active clients as JSON
blesta extract clients getList --param status=active

# Stream all invoices as JSONL
blesta extract invoices getList --format jsonl

# Export all packages as CSV
blesta extract packages getAll --format csv
```

---

### `blesta report`

Fetch a Blesta report for a date range. CSV responses are returned as a JSON array of row
dicts; JSON responses are returned as-is.

```
blesta report <type> --start YYYY-MM-DD --end YYYY-MM-DD [--param key=value ...]
```

**Available report types** (depends on your Blesta installation):

| Type | Description |
|------|-------------|
| `package_revenue` | Revenue by package |
| `tax_liability` | Tax liability by period |
| `invoice_aging` | Invoice aging summary |
| `client_data_portability` | GDPR-style data export |

**Examples:**

```bash
# Q1 2025 revenue report
blesta report package_revenue --start 2025-01-01 --end 2025-03-31

# Tax liability for January
blesta report tax_liability --start 2025-01-01 --end 2025-01-31
```

---

### `blesta discover`

Introspect the bundled API schema without making API calls.

```
blesta discover models
blesta discover methods <model>
blesta discover spec <model> <method>
```

**Examples:**

```bash
# List all 71 available models
blesta discover models

# List all methods for the Clients model
blesta discover methods clients

# Show full spec for clients.getList
blesta discover spec clients getList
```

The `spec` subcommand returns a JSON object with `http_method`, `params`, `return_type`,
`description`, and `source` fields.

---

## Legacy Mode

The original single-command form is still supported:

```
blesta --model <model> --method <method> [--action GET|POST|PUT|DELETE] [--params key=value ...] [--last-request]
```

**Examples:**

```bash
blesta --model clients --method getList --params status=active
blesta --model clients --method get --params client_id=1
blesta --model clients --method create --action POST --params firstname=John lastname=Doe
blesta --model clients --method getList --last-request
```

`--last-request` prints the URL and arguments of the most recent request, with sensitive
fields (API keys, passwords, tokens) automatically redacted as `"***"`.

---

## Output and Errors

All output is JSON to stdout. Errors produce a JSON error object on stdout and exit with
code 1:

```json
{"error": "Blesta returned errors: ...", "exit_code": 1}
```

Pipe to `jq` for filtering:

```bash
blesta extract clients getList --format jsonl | jq '.id'
```

---

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BLESTA_API_URL` | Yes | — | API base URL (`https://domain.com/api`) |
| `BLESTA_API_USER` | Yes | — | API username |
| `BLESTA_API_KEY` | Yes | — | API key |
| `BLESTA_AUTH_METHOD` | No | `basic` | `basic` or `header` |
| `BLESTA_ALLOW_HTTP` | No | unset | Set to `1`, `true`, `yes`, or `on` to permit `http://` base URLs (local/dev only; HTTPS is enforced by default) |

See [`SDK_USAGE.md`](SDK_USAGE.md) for the full programmatic API reference.
