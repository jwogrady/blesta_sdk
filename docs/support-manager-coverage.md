# Support Manager schema coverage

What the bundled plugin schema covers for Blesta's Support Manager plugin, where it
came from, and — the part that matters most to a consumer — **what the upstream API
does not document.**

Tracking issue: [#108](https://github.com/jwogrady/blesta_sdk/issues/108).

## Where it comes from

Support Manager ships **inside the Blesta core distribution**, not as a public
`blesta/plugin-*` repository — `blesta/plugin-support_manager` does not exist and does
not appear in the `blesta` organisation's repository listing. So the PHP-docblock
extraction path used for `cms`, `domains`, `extension_generator`, `softaculous` and
`webhooks` cannot reach it.

Instead, these models are extracted from Blesta's generated class documentation at
<https://source-docs.blesta.com/>, which carries the same docblocks. Each model records
`"source_type": "phpdocumentor_html"` and a `"source"` URL pointing at the exact class
page it was read from, so a consumer can tell a documented parameter from an inferred
one and can go and check.

`category` and `http_method` on every method remain **inferred** from the method-name
prefix (`prefix_rules_v1`, declared in the schema's `metadata.inference`). They are not
upstream statements.

## Models covered

Model keys are the API path segments. A request goes to
`/support_manager.support_manager_tickets/getList.json`, per Blesta's documented
plugin-model convention (`/plugin.model/method.format`).

| Model key | What it carries |
|---|---|
| `support_manager.support_manager_tickets` | Tickets, replies, statuses, priorities, attachments |
| `support_manager.support_manager_departments` | Departments and their settings |
| `support_manager.support_manager_staff` | Staff assignment, schedules, settings |
| `support_manager.support_manager_responses` | Predefined responses and categories |
| `support_manager.support_manager_kb_articles` | Knowledge base articles |
| `support_manager.support_manager_kb_categories` | Knowledge base categories |
| `support_manager.support_manager_settings` | Plugin settings |

## The ticket extraction surface

| Need | Method | Notes |
|---|---|---|
| Tickets for one client | `getList(status, staff_id, client_id, page, order_by, get_replies, reply_types, filters)` | `client_id` is a first-class optional parameter. `status` is **required** — use `not_closed` for all open states, or iterate `getStatuses()` |
| Row count for paging | `getListCount(status, staff_id, client_id, filters)` | Registered as the pagination pair of `getList`, so `suggest_pagination_pair()` and `count_for()` work |
| One ticket | `get(ticket_id, get_replies, reply_types, staff_id)` | |
| Ticket by its public code | `getTicketByCode(code, get_replies, reply_types)` | |
| Ticket history | `get_replies=True` on `get`/`getList`, plus `reply_types` | Reply types are `reply`, `note`, `log`; `log` entries are the "loggable changes" recorded by `edit()`'s `log` parameter |
| Status / priority vocabularies | `getStatuses()`, `getPriorities()`, `getReplyTypes()` | Read these rather than hard-coding the strings |
| Department, priority, staff, recency filters | `filters` on `getList`/`getListCount` | Documented keys: `ticket_number`, `priority`, `department_id`, `summary`, `assigned_staff`, `last_reply` |
| Counts by status | `getStatusCount(status, staff_id, client_id, filters)` | |
| Search | `search(query, staff_id, page, order_by)`, `searchByCode(...)`, `getSearchCount(query, staff_id)` | |
| Attachments | `getAttachments(ticket_id, reply_id)`, `getAttachment(attachment_id)` | |

Departments (`getList(company_id, page, order_by)`, `get`, `getAll`) resolve a
`department_id` to a name; staff (`getList`, `get`, `getAll`) resolves `assigned_staff`.

## Gaps — what upstream does not expose

These are recorded rather than guessed. **No schema method was invented to fill them.**
`TestSupportManagerCoverage::test_documented_gaps_still_hold` asserts each absence, so
if Blesta starts documenting one of these the test goes red and this file is what needs
updating.

1. **No read filter on service.** Ticket/service linkage is *writable* — `add()` and
   `edit()` both document a `service_id` var, and `validateClientService(service_id,
   client_id)` confirms the association is enforced — but there is **no documented way
   to list or filter tickets by service.** `service_id` is not among the documented
   `filters` keys on `getList`/`getListCount`, and no API-category method takes a
   `service_id` parameter. A consumer needing tickets-per-service must fetch by
   `client_id` and group client-side on whatever the ticket object carries.

2. **The ticket object's fields are not documented.** `get()` returns `mixed` and
   `getList()` returns `array<string|int, mixed>`, with no `@return` field list on
   either. So the docs do not state which columns a ticket row carries — including
   whether `service_id`, `date_added`, `date_closed` or `last_reply_date` appear on it.
   `order_by` defaults to `['last_reply_date' => 'desc']`, which is good evidence that
   `last_reply_date` is present, but that is inference. **Confirm the field set against
   a live install before depending on it.** The same applies to the shape of a reply.

3. **Reply-type sub-fields parse as one malformed entry.** The `reply_types` parameter's
   documented values (`"reply"`, `"note"`, `"log"`) are written as a single docblock
   line, so the extractor records one field named `"reply",` with the rest as its
   description. `getReplyTypes()` is the reliable source; do not read the `fields` list
   on that parameter.

4. **Custom fields are opaque.** `add()`/`edit()` document a `custom_fields` var keyed
   by field id, but the ids and their meanings are per-installation and not in any
   schema. `support_manager.support_manager_departments` is where field definitions
   live; resolving them is a runtime step.

5. **Client-side vs staff-side visibility is not modelled.** Several methods take an
   optional `staff_id` that narrows results to the departments that staff member can
   see. Omitting it is not documented as "no restriction" in every case. If a count and
   a list disagree, check that both calls passed the same `staff_id`.

6. **`category` is inferred, not upstream.** Methods classified `internal` (the
   `validate*` family) are still public PHP methods and therefore still callable through
   the API — Blesta's API exposes every public model method. The `internal` label is this
   SDK's prefix heuristic saying "not intended as an entry point", not an upstream
   guarantee that it is unreachable.

## Refreshing

```bash
uv run python -m tools.extract_plugin_schema
```

`SOURCE_DOCS_REGISTRY` in `tools/extract_plugin_schema.py` maps each plugin directory to
its `(model file basename, documented class name)` pairs. The **basename** is the API
path segment; the class name only locates the documentation page. Both come from the
`public_html/plugins/support_manager/models/…` path recorded on each class page, not
from transliterating the class name.
