"""MCP prompt templates for the Blesta SDK server.

Prompts help AI agents understand how to use the Blesta SDK tools
for common workflows such as auditing clients, planning migrations,
or reconciling invoices.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template strings
# ---------------------------------------------------------------------------

AUDIT_CLIENT_PROMPT = """\
You are auditing a Blesta client record. Use the following tools in order:

1. blesta_call(model="Clients", method="get", params={{"client_id": "<client_id>"}})
   → Fetch the client's basic record.

2. blesta_call(model="Invoices", method="getList",
   params={{"client_id": "<client_id>"}})
   → Fetch open invoices.

3. blesta_call(model="Services", method="getList",
   params={{"client_id": "<client_id>"}})
   → Fetch active services.

Summarise the client's account status, outstanding balance, and service list.
"""

PLAN_MIGRATION_PROMPT = """\
You are planning a data migration from one Blesta instance to another.

Use blesta_list_models() to discover all available models.
Use blesta_get_method_spec() to understand the read methods for each model.

For each model:
- Identify the list method (typically getList).
- Identify any required parameters.
- Estimate record counts with blesta_count().

Produce a migration plan that lists models in dependency order.
"""

RECONCILE_INVOICES_PROMPT = """\
You are reconciling Blesta invoices against payment records.

1. blesta_get_all(model="Invoices", method="getList", params={{"status": "unpaid"}})
   → Fetch all unpaid invoices.

2. For each invoice, call blesta_call(model="Transactions", method="getList",
   params={{"invoice_id": "<id>"}}) to check for matching transactions.

Report any invoices that lack matching transactions.

Note: This SDK is read-only in this context. Do not attempt to create or
modify records unless explicitly authorised.
"""

EXTRACT_CUSTOMER_SNAPSHOT_PROMPT = """\
Extract a complete snapshot of a Blesta customer for export.

Use blesta_extract with these targets:
- ["Clients", "getList"]
- ["Contacts", "getList"]
- ["Services", "getList"]
- ["Invoices", "getList"]

Then use blesta_capabilities_report() to understand what other models
might contain relevant customer data.
"""

MAP_TO_PRIME_ACCOUNT_PROMPT = """\
You are mapping Blesta client records to a target billing system.

1. Use blesta_list_models() to discover all models.
2. For client-related models, use blesta_get_method_spec() to understand fields.
3. Extract client data with blesta_get_all().
4. Produce a field-mapping document showing Blesta field names → target system
   field names.

Note: Field names visible in API responses may differ from schema param names.
Always verify with a live sample.
"""

# ---------------------------------------------------------------------------
# Prompt registry
# ---------------------------------------------------------------------------

PROMPT_REGISTRY: list[tuple[str, str, str]] = [
    ("blesta_audit_client", AUDIT_CLIENT_PROMPT, "Audit a Blesta client account"),
    ("blesta_plan_migration", PLAN_MIGRATION_PROMPT, "Plan a Blesta data migration"),
    (
        "blesta_reconcile_invoices",
        RECONCILE_INVOICES_PROMPT,
        "Reconcile Blesta invoices against payments",
    ),
    (
        "blesta_extract_customer_snapshot",
        EXTRACT_CUSTOMER_SNAPSHOT_PROMPT,
        "Extract a full customer snapshot",
    ),
    (
        "blesta_map_to_prime_account",
        MAP_TO_PRIME_ACCOUNT_PROMPT,
        "Map Blesta fields to a target billing system",
    ),
]


def register_prompts(mcp_server: Any) -> None:
    """Register all Blesta prompts on *mcp_server*.

    :param mcp_server: A :class:`mcp.server.fastmcp.FastMCP` instance.
    """
    for name, template, description in PROMPT_REGISTRY:
        mcp_server.prompt(name=name, description=description)(lambda t=template: t)
    logger.debug("Registered %d MCP prompts", len(PROMPT_REGISTRY))
