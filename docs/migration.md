# Migration Idempotency Design

This document describes the agreed strategy for migrating data between Blesta
instances (or from external billing platforms) without duplicating financial
records.

---

## Core Principle

**Every migration must be safe to restart.**

A partially completed migration — interrupted by a crash, network error, or
operator stop — must be resumable from any point without creating duplicate
clients, invoices, services, transactions, or payment accounts.

---

## Strategy: Migration Ledger + Check-Then-Create + Source IDs

### 1. Migration Ledger

Maintain an external table (database, CSV, or JSON file) that maps source IDs
to target IDs:

| Column | Description |
|--------|-------------|
| `source_blesta_client_id` | Client ID in the source system |
| `target_blesta_client_id` | Client ID created in the target Blesta |
| `source_invoice_id` | Invoice ID in the source system |
| `target_invoice_id` | Invoice ID created in the target Blesta |
| `source_service_id` | Service ID in the source system |
| `target_service_id` | Service ID created in the target Blesta |
| `source_transaction_id` | Transaction ID in the source system |
| `target_transaction_id` | Transaction ID created in the target Blesta |
| `migrated_at` | Timestamp when the record was created in the target |

Before creating any record, **check the ledger first**. If a mapping already
exists, skip creation and use the existing target ID.

### 2. Check-Then-Create

Before calling any POST endpoint that creates a record, query the target system
to confirm the record does not already exist:

```python
# Example: migrate a client
def migrate_client(source_client, ledger, api):
    # 1. Check ledger first
    if ledger.has_client(source_client["id"]):
        target_id = ledger.get_client(source_client["id"])
        return target_id  # already migrated

    # 2. Search by source_id custom field
    existing = api.get("clients", "getList", {
        "custom_fields[source_id]": source_client["id"]
    })
    if existing.data:
        target_id = existing.data[0]["id"]
        ledger.record_client(source_client["id"], target_id)
        return target_id

    # 3. Create the client
    response = api.post("clients", "create", {
        **source_client,
        "custom_fields[source_id]": source_client["id"],
    })
    target_id = response.data["id"]
    ledger.record_client(source_client["id"], target_id)
    return target_id
```

### 3. Source IDs via Custom Fields

Pass `source_id` (or an `external_ref`) in Blesta `custom_fields` when
creating records. This allows idempotent lookup even if the migration ledger
is lost:

```python
api.post("clients", "create", {
    "first_name": "Alice",
    "custom_fields[source_id]": "prime_12345",
})
```

Always query by `custom_fields[source_id]` before creating, so re-running the
migration script skips already-migrated records.

---

## Entity Migration Order

Respect referential integrity by migrating in this order:

1. **Clients** — no dependencies
2. **Contacts** — depends on clients
3. **Services** — depends on clients and packages
4. **Invoices** — depends on clients
5. **Invoice Line Items** — depends on invoices
6. **Transactions** — depends on clients and invoices
7. **Payment Accounts** — depends on clients

---

## What NOT to Do

- **Do not use `retry_mutations=True` as an idempotency mechanism.**
  A 5xx response after a POST does not mean the record was not created.
  Retrying will create duplicates. The SDK does not retry mutations on 5xx
  for exactly this reason.

- **Do not assume a failed POST means no record was created.**
  Network timeouts and server errors can occur after Blesta processes the
  write. Always check-then-create on restart.

- **Do not run migration scripts in parallel against the same entity type**
  unless you have a distributed lock or partition the records by range.

---

## Restartability Checklist

- [ ] Migration ledger is persisted externally (not in-memory).
- [ ] Every entity is checked against the ledger before creation.
- [ ] Custom `source_id` field is set on every created record.
- [ ] The script can be killed and restarted at any point.
- [ ] Running the script twice produces the same result (idempotent).
- [ ] No financial records (invoices, transactions) are created twice.

---

## SDK Usage Note

When migrating, prefer:

```python
api = BlestaRequest(url, user, key, raise_on_error=True)
```

This surfaces Blesta validation errors immediately rather than returning
HTTP 200 responses that contain `{"errors": {...}}` in the body.

See also: [SDK_USAGE.md](../SDK_USAGE.md)
